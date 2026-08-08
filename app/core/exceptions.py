class HereshkoError(Exception): 
    pass

class IngestionError(HereshkoError): 
    pass

class UnsupportedSourceError(IngestionError): 
    pass

class ChunkingError(HereshkoError): 
    pass

class RetrievalError(HereshkoError): 
    pass