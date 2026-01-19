# projects/modulo2/rate_limiter.py
"""
Rate Limiter para controlar requisições ao SEFAZ e evitar penalizações.

Limites recomendados pela SEFAZ:
- Máximo 10 requisições por minuto por CNPJ
- Máximo 100 requisições por hora por CNPJ
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional
import threading


class SEFAZRateLimiter:
    """
    Controla a taxa de requisições ao SEFAZ para evitar penalizações.
    Thread-safe para uso em ambiente multi-threaded.
    """
    
    def __init__(
        self,
        max_per_minute: int = 10,
        max_per_hour: int = 100,
        delay_between_requests: float = 6.0
    ):
        """
        Args:
            max_per_minute: Máximo de requisições por minuto (padrão: 10)
            max_per_hour: Máximo de requisições por hora (padrão: 100)
            delay_between_requests: Delay mínimo entre requisições em segundos (padrão: 6.0)
        """
        self.max_per_minute = max_per_minute
        self.max_per_hour = max_per_hour
        self.delay_between_requests = delay_between_requests
        
        # Thread-safe storage
        self._lock = threading.Lock()
        self._requests_minute = defaultdict(list)  # CNPJ -> [datetime, ...]
        self._requests_hour = defaultdict(list)    # CNPJ -> [datetime, ...]
        self._last_request_time = {}               # CNPJ -> datetime
    
    def _clean_old_requests(self, cnpj_clean: str, now: datetime):
        """Remove requisições antigas dos registros."""
        # Limpar requisições com mais de 1 minuto
        self._requests_minute[cnpj_clean] = [
            r for r in self._requests_minute[cnpj_clean]
            if now - r < timedelta(minutes=1)
        ]
        
        # Limpar requisições com mais de 1 hora
        self._requests_hour[cnpj_clean] = [
            r for r in self._requests_hour[cnpj_clean]
            if now - r < timedelta(hours=1)
        ]
    
    def _normalize_cnpj(self, cnpj: str) -> str:
        """Remove formatação do CNPJ."""
        return cnpj.replace(".", "").replace("/", "").replace("-", "").strip()
    
    def _can_request_internal(self, cnpj_clean: str, now: datetime) -> bool:
        """
        Versão interna de can_request que não adquire lock (deve ser chamada dentro do lock).
        """
        # Limpar requisições antigas
        self._clean_old_requests(cnpj_clean, now)
        
        # Verificar limite por minuto
        if len(self._requests_minute[cnpj_clean]) >= self.max_per_minute:
            return False
        
        # Verificar limite por hora
        if len(self._requests_hour[cnpj_clean]) >= self.max_per_hour:
            return False
        
        return True
    
    def can_request(self, cnpj: str) -> bool:
        """
        Verifica se uma nova requisição pode ser feita para o CNPJ.
        
        Returns:
            True se pode fazer requisição, False caso contrário
        """
        with self._lock:
            now = datetime.now()
            cnpj_clean = self._normalize_cnpj(cnpj)
            return self._can_request_internal(cnpj_clean, now)
    
    def wait_if_needed(self, cnpj: str) -> float:
        """
        Aguarda o tempo necessário antes de fazer uma requisição.
        Retorna o tempo de espera em segundos.
        
        Returns:
            Tempo de espera em segundos (0 se não precisa esperar)
        """
        print(f"[RATE LIMITER] wait_if_needed chamado para CNPJ {cnpj[:8]}...")
        print(f"[RATE LIMITER] Tentando adquirir lock...")
        with self._lock:
            print(f"[RATE LIMITER] Lock adquirido, processando...")
            now = datetime.now()
            cnpj_clean = self._normalize_cnpj(cnpj)
            print(f"[RATE LIMITER] CNPJ normalizado: {cnpj_clean[:8]}")
            
            wait_time = 0.0
            
            print(f"[RATE LIMITER] Verificando delay mínimo entre requisições...")
            # Verificar delay mínimo entre requisições
            if cnpj_clean in self._last_request_time:
                last_time = self._last_request_time[cnpj_clean]
                elapsed = (now - last_time).total_seconds()
                
                if elapsed < self.delay_between_requests:
                    wait_time = self.delay_between_requests - elapsed
                    print(f"[RATE LIMITER] Delay mínimo necessário: {wait_time:.1f}s")
            
            print(f"[RATE LIMITER] Verificando limites de taxa...")
            # Verificar se precisa aguardar por limite de taxa (usar versão interna para evitar deadlock)
            if not self._can_request_internal(cnpj_clean, now):
                print(f"[RATE LIMITER] Limite de taxa atingido, calculando tempo de espera...")
                # Calcular tempo até a requisição mais antiga sair da janela
                if self._requests_minute[cnpj_clean]:
                    oldest_minute = min(self._requests_minute[cnpj_clean])
                    time_until_oldest_expires = (oldest_minute + timedelta(minutes=1) - now).total_seconds()
                    wait_time = max(wait_time, max(0, time_until_oldest_expires) + 1)
                    print(f"[RATE LIMITER] Tempo até limite de minuto expirar: {time_until_oldest_expires:.1f}s")
                
                if self._requests_hour[cnpj_clean]:
                    oldest_hour = min(self._requests_hour[cnpj_clean])
                    time_until_oldest_expires = (oldest_hour + timedelta(hours=1) - now).total_seconds()
                    wait_time = max(wait_time, max(0, time_until_oldest_expires) + 1)
                    print(f"[RATE LIMITER] Tempo até limite de hora expirar: {time_until_oldest_expires:.1f}s")
            
            # Aguardar se necessário
            if wait_time > 0:
                print(f"[RATE LIMITER] Aguardando {wait_time:.1f}s antes de consultar CNPJ {cnpj_clean[:8]}...")
                time.sleep(wait_time)
            
            return wait_time
    
    def record_request(self, cnpj: str):
        """Registra que uma requisição foi feita."""
        with self._lock:
            now = datetime.now()
            cnpj_clean = self._normalize_cnpj(cnpj)
            
            # Registrar requisição
            self._requests_minute[cnpj_clean].append(now)
            self._requests_hour[cnpj_clean].append(now)
            self._last_request_time[cnpj_clean] = now
            
            # Limpar requisições antigas
            self._clean_old_requests(cnpj_clean, now)
    
    def get_stats(self, cnpj: str) -> dict:
        """
        Retorna estatísticas de requisições para um CNPJ.
        
        Returns:
            dict com estatísticas (requests_last_minute, requests_last_hour, etc.)
        """
        with self._lock:
            now = datetime.now()
            cnpj_clean = self._normalize_cnpj(cnpj)
            
            self._clean_old_requests(cnpj_clean, now)
            
            return {
                "cnpj": cnpj_clean,
                "requests_last_minute": len(self._requests_minute[cnpj_clean]),
                "requests_last_hour": len(self._requests_hour[cnpj_clean]),
                "limit_per_minute": self.max_per_minute,
                "limit_per_hour": self.max_per_hour,
                "can_request": self._can_request_internal(cnpj_clean, now),
                "last_request": self._last_request_time.get(cnpj_clean)
            }


# Instância global do rate limiter
# Pode ser customizada via variável de ambiente no futuro
_rate_limiter_instance: Optional[SEFAZRateLimiter] = None


def get_rate_limiter() -> SEFAZRateLimiter:
    """Retorna instância global do rate limiter (singleton)."""
    global _rate_limiter_instance
    
    if _rate_limiter_instance is None:
        # Em DEV mode, usar limites mais permissivos
        from .config import DEV_MODE
        
        if DEV_MODE:
            # Em DEV, não há restrições (mocks locais)
            _rate_limiter_instance = SEFAZRateLimiter(
                max_per_minute=1000,  # Muito alto em DEV
                max_per_hour=10000,
                delay_between_requests=0.1  # Delay mínimo
            )
        else:
            # Em PROD, usar limites ULTRA CONSERVADORES para evitar bloqueio SEFAZ
            # O SEFAZ bloqueia por 1 hora após excesso de requisições
            _rate_limiter_instance = SEFAZRateLimiter(
                max_per_minute=3,   # Apenas 3 req/min (muito abaixo do limite de 10)
                max_per_hour=50,    # 50 req/hora (metade do limite de 100)
                delay_between_requests=20.0  # 20 segundos entre requisições
            )
    
    return _rate_limiter_instance


# Função de conveniência para uso no código
def wait_before_sefaz_request(cnpj: str) -> float:
    """
    Aguarda antes de fazer uma requisição ao SEFAZ.
    Retorna o tempo de espera em segundos.
    
    Usage:
        wait_before_sefaz_request(cnpj)
        # Fazer requisição SEFAZ aqui
        get_rate_limiter().record_request(cnpj)
    """
    limiter = get_rate_limiter()
    return limiter.wait_if_needed(cnpj)
