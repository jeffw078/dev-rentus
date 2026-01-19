# projects/modulo2/preview_cache.py
"""
Cache temporario para XMLs consultados no preview.
Evita re-consultar SEFAZ quando usuario confirma importacao imediatamente apos preview.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import threading

class PreviewCache:
    """Cache thread-safe para armazenar XMLs consultados no preview"""
    
    def __init__(self, ttl_minutes: int = 15):
        """
        Args:
            ttl_minutes: Tempo de vida do cache em minutos (padrao: 15)
        """
        self._cache: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self._ttl = timedelta(minutes=ttl_minutes)
    
    def set(self, xmls_por_empresa: Dict[str, List[dict]], nsu_por_empresa: Dict[str, int]):
        """
        Armazena XMLs consultados no preview.
        
        Args:
            xmls_por_empresa: {cnpj: [lista de XMLs]}
            nsu_por_empresa: {cnpj: maior_nsu}
        """
        with self._lock:
            self._cache = {
                'xmls': xmls_por_empresa,
                'nsus': nsu_por_empresa,
                'timestamp': datetime.now()
            }
            print(f"[CACHE] Armazenados {sum(len(x) for x in xmls_por_empresa.values())} XMLs de {len(xmls_por_empresa)} empresas")
    
    def get(self) -> Optional[tuple]:
        """
        Recupera XMLs do cache se ainda valido.
        
        Returns:
            (xmls_por_empresa, nsu_por_empresa) ou None se cache expirado
        """
        with self._lock:
            if not self._cache:
                print("[CACHE] Cache vazio")
                return None
            
            timestamp = self._cache.get('timestamp')
            if not timestamp:
                print("[CACHE] Cache invalido (sem timestamp)")
                return None
            
            age = datetime.now() - timestamp
            if age > self._ttl:
                print(f"[CACHE] Cache expirado ({age.total_seconds():.0f}s > {self._ttl.total_seconds():.0f}s)")
                self._cache = {}
                return None
            
            print(f"[CACHE] Cache valido (idade: {age.total_seconds():.0f}s)")
            return (self._cache['xmls'], self._cache['nsus'])
    
    def clear(self):
        """Limpa o cache"""
        with self._lock:
            if self._cache:
                print("[CACHE] Cache limpo")
            self._cache = {}
    
    def has_valid_cache(self) -> bool:
        """Verifica se existe cache valido"""
        return self.get() is not None


# Instancia global do cache
_preview_cache = PreviewCache(ttl_minutes=15)

def get_preview_cache() -> PreviewCache:
    """Retorna a instancia global do cache"""
    return _preview_cache
