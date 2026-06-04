class LLMClientError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class LLMRateLimitError(LLMClientError):
    pass


class LLMAuthenticationError(LLMClientError):
    pass


class LLMInvalidRequestError(LLMClientError):
    pass
