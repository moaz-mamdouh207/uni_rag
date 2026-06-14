from modules.chat.schemas import CitationMetaData
class AgentState:
    def __init__(self):
        self.chunk_cache: dict[str, CitationMetaData] = {}