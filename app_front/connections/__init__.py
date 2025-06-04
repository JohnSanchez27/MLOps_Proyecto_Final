import connections.connections as connections
from functools import lru_cache

@lru_cache()
def getConnections():
    
    return connections.engine_raw_data, connections.engine_clean_data

connectionsdb = getConnections()