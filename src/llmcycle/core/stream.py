import logging
from typing import AsyncGenerator
from llmcycle.schema import CompletionRequest, Message
from llmcycle.providers.base import LLMProvider
from llmcycle.core.router import ModelRouter
from llmcycle.core.keys import KeyManager

logger = logging.getLogger(__name__)

class StreamResilienceManager:
    """
    Handles streaming failover.
    If a stream disconnects mid-response, this manager will capture
    the text already generated, switch to a fallback model, append
    the generated text to the assistant's context, and resume the stream.
    """
    
    def __init__(
        self, 
        router: ModelRouter, 
        key_manager: KeyManager, 
        providers: dict[str, LLMProvider]
    ):
        self.router = router
        self.key_manager = key_manager
        self.providers = providers # map of model -> LLMProvider instance (simplified)

    async def safe_stream(self, request: CompletionRequest) -> AsyncGenerator[str, None]:
        models_to_try = self.router.get_route(request.model)
        generated_text_so_far = ""
        
        for model in models_to_try:
            if model not in self.providers:
                logger.warning(f"No provider found for model {model}")
                continue
                
            provider = self.providers[model]
            api_key = self.key_manager.get_next_key(model) # Assumes provider uses model name for key lookups for simplicity
            
            if not api_key:
                logger.warning(f"No active API keys available for model {model}")
                continue
                
            try:
                # If we're failing over mid-stream, we must update the prompt
                # to include the generated_text_so_far
                current_request = request.model_copy(deep=True)
                current_request.model = model
                
                if generated_text_so_far:
                    current_request.messages.append(
                        Message(role="assistant", content=generated_text_so_far)
                    )
                    # Ideally, you'd instruct the fallback model to continue from here
                    current_request.messages.append(
                        Message(role="user", content="Continue exactly from the last assistant message. Do not repeat anything. Just continue.")
                    )

                logger.info(f"Attempting stream with model {model}")
                stream_gen = provider.generate_stream(current_request, api_key)
                
                async for chunk in stream_gen:
                    generated_text_so_far += chunk
                    yield chunk
                    
                # If we finish the stream without exceptions, we are done!
                return
                
            except Exception as e:
                logger.error(f"Stream interrupted on model {model}: {e}")
                self.key_manager.report_error(api_key, "connection_error")
                logger.info("Failing over to next model in sequence...")
                # The loop will continue and try the next model
        
        # If we exit the loop, all models failed
        if not generated_text_so_far:
            raise RuntimeError("All models failed and no text was generated.")
        else:
            logger.error("All models failed, but some text was generated.")
