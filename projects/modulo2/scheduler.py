# projects/modulo2/scheduler.py

import schedule
import time
import threading
from datetime import datetime

from .service import importar_xmls_diario_automatico


class SEFAZScheduler:
    """Agendador para importação automática diária de XMLs do SEFAZ"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.xmls_disponiveis = 0
        self.ultima_verificacao = None
        
    def job_diario(self):
        """Job executado diariamente às 00:00 - APENAS VERIFICA, NÃO IMPORTA"""
        print(f"[SCHEDULER] Verificando XMLs disponíveis - {datetime.now()}")
        try:
            # Apenas verificar quantidade, NÃO importar automaticamente
            from .preview import preview_importacao
            result = preview_importacao()
            
            if result.get("status") == "success":
                total_disponiveis = result.get("total_encontrado", 0)
                print(f"[SCHEDULER] {total_disponiveis} XMLs novos disponíveis para importação")
                
                # Armazenar informação para exibir no frontend
                self.xmls_disponiveis = total_disponiveis
                self.ultima_verificacao = datetime.now()
            else:
                print(f"[SCHEDULER] ERRO ao verificar XMLs: {result.get('mensagem', 'Erro desconhecido')}")
                self.xmls_disponiveis = 0
        except Exception as e:
            print(f"[SCHEDULER] ERRO CRÍTICO no job diário: {e}")
            import traceback
            traceback.print_exc()
            self.xmls_disponiveis = 0
    
    def start(self):
        """Inicia o agendador em thread separada"""
        if self.running:
            print("[SCHEDULER] Agendador já está em execução")
            return
        
        print("[SCHEDULER] Iniciando agendador de verificação automática...")
        
        # Agendar job diário às 00:00
        schedule.every().day.at("00:00").do(self.job_diario)
        
        print("[SCHEDULER] Job agendado: Verificação diária de novos XMLs às 00:00")
        
        self.running = True
        
        # Executar em thread separada para não bloquear
        def run_scheduler():
            try:
                while self.running:
                    schedule.run_pending()
                    time.sleep(60)  # Verificar a cada 1 minuto
            except Exception as e:
                print(f"[SCHEDULER] ERRO CRÍTICO na thread do scheduler: {e}")
                import traceback
                traceback.print_exc()
                self.running = False  # Marcar como parado em caso de erro
        
        self.thread = threading.Thread(target=run_scheduler, daemon=True)
        self.thread.start()
        
        # Aguardar um pouco para confirmar que a thread iniciou
        time.sleep(0.1)
        if not self.thread.is_alive():
            self.running = False
            raise RuntimeError("Falha ao iniciar thread do scheduler")
        
        print("[SCHEDULER] Agendador iniciado com sucesso")
    
    def stop(self):
        """Para o agendador"""
        print("[SCHEDULER] Parando agendador...")
        self.running = False
        schedule.clear()
        if self.thread:
            self.thread.join(timeout=5)
        print("[SCHEDULER] Agendador parado")
    
    def get_next_run(self):
        """Retorna próxima execução agendada"""
        jobs = schedule.jobs
        if jobs:
            return jobs[0].next_run
        return None
    
    def get_status(self):
        """Retorna status do agendador"""
        # Verificar se a thread está realmente viva
        thread_alive = self.thread is not None and self.thread.is_alive()
        
        # Se self.running está True mas a thread morreu, corrigir o estado
        # (não reiniciar automaticamente aqui para evitar problemas de concorrência)
        if self.running and not thread_alive:
            print("[SCHEDULER] AVISO: Thread do scheduler morreu! Status: running=False")
            self.running = False
        
        return {
            "running": self.running and thread_alive,
            "thread_alive": thread_alive,
            "next_run": self.get_next_run().isoformat() if self.get_next_run() else None,
            "xmls_disponiveis": self.xmls_disponiveis,
            "ultima_verificacao": self.ultima_verificacao.isoformat() if self.ultima_verificacao else None,
            "jobs_count": len(schedule.jobs)
        }


# Instância global do scheduler
_scheduler_instance = None


def get_scheduler() -> SEFAZScheduler:
    """Retorna instância global do scheduler"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SEFAZScheduler()
    return _scheduler_instance


def start_scheduler():
    """Inicia o scheduler global"""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler():
    """Para o scheduler global"""
    scheduler = get_scheduler()
    scheduler.stop()
