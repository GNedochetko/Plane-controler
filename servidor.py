from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Condition, Event, Thread
import time

import grpc

import controle_pb2 as pb
import controle_pb2_grpc as rpc
from painel import Painel

ENDERECO = "0.0.0.0:50051"
DURACAO_OPERACAO = 5 

#Torre herda da classe gerada pelo gRPC.
class Torre(rpc.ControleTrafegoServicer):
    def __init__(self, duracao=DURACAO_OPERACAO):
        self.duracao = duracao
        self.fila = deque()
        self.atual = None
        self.eventos = deque(maxlen=60)
        self.condicao = Condition()
        self.parar = Event()
        self._registrar("Torre iniciada. Aguardando aeronaves.")
        #o construtor inicia o trabalhador
        self._trabalhador = Thread(target=self._atender_fila, daemon=True)
        self._trabalhador.start()

    def _registrar(self, mensagem):
        self.eventos.append(f"{datetime.now():%H:%M:%S}  {mensagem}")
        print(mensagem, flush=True)

    def SolicitarOperacao(self, pedido, contexto):
        identificador = pedido.aeronave_id.strip()
        operacao = pedido.operacao.strip().lower()

        voo = {"id": identificador, "operacao": operacao, "estado": "aguardando"}
        #adquire um bloqueio pra colocar o voo na fila
        with self.condicao:
            if self.parar.is_set():
                contexto.abort(grpc.StatusCode.UNAVAILABLE, "A torre está encerrando.")
            self.fila.append(voo)
            self._registrar(f"{identificador} solicitou {operacao} e entrou na fila.")
            self.condicao.notify_all()

        anterior = None
        try:
            while contexto.is_active() and not self.parar.is_set():
                #adquire um bloqueio
                with self.condicao:
                    posicao = self.fila.index(voo) + 1 if voo["estado"] == "aguardando" else 0
                    estado = (voo["estado"], posicao)
                    if estado == anterior:
                        #Durante essa espera, o bloqueio é liberado
                        self.condicao.wait(timeout=0.2)
                        continue
                    anterior = estado
                    if estado[0] == "aguardando":
                        mensagem = f"{identificador}: aguardando, posição {posicao} na fila."
                    elif estado[0] == "em_operacao":
                        mensagem = f"{identificador}: operação de {operacao} autorizada; utilizando a pista."
                    else:
                        mensagem = f"{identificador}: operação de {operacao} concluída."

                #O yield é o que permite o streaming de respostas
                yield pb.Atualizacao(estado=estado[0], posicao_fila=posicao, mensagem=mensagem)
                if estado[0] == "finalizada":
                    return
        finally:
            with self.condicao:
                #Se o cliente desconectar enquanto espera, seu pedido sai da fila
                if voo["estado"] == "aguardando":
                    self.fila.remove(voo)
                    self._registrar(f"{identificador} desconectou e saiu da fila.")
                    self.condicao.notify_all()

    def _atender_fila(self):
        while not self.parar.is_set():
            with self.condicao:
                self.condicao.wait_for(lambda: self.fila or self.parar.is_set())
                if self.parar.is_set():
                    return
                self.atual = self.fila.popleft()
                self.atual["estado"] = "em_operacao"
                #um relógio adequado para medir intervalos, pois não acompanha ajustes no horário do computador
                self.atual["inicio"] = time.monotonic()
                self._registrar(f"{self.atual['id']}: operação de {self.atual['operacao']} autorizada. Pista ocupada.")
                self.condicao.notify_all()

            # A torre simula a operação mesmo se o cliente fechar sua conexão.
            # A pista só é liberada depois do tempo completo da operação.
            if self.parar.wait(self.duracao):
                return
            with self.condicao:
                self.atual["estado"] = "finalizada"
                self._registrar(f"{self.atual['id']}: operação concluída. Pista liberada.")
                self.atual = None
                self.condicao.notify_all()

    def fotografia(self):
        #fornece ao painel uma cópia consistente do estado.
        with self.condicao:
            atual = dict(self.atual) if self.atual is not None else None
            if atual is not None:
                atual["progresso"] = min((time.monotonic() - atual["inicio"]) / self.duracao, 1)
            return {
                "atual": atual,
                "fila": [(voo["id"], voo["operacao"]) for voo in self.fila],
                "eventos": list(self.eventos),
            }

    def encerrar(self):
        self.parar.set()
        with self.condicao:
            self.condicao.notify_all()
        self._trabalhador.join(timeout=1)


def criar_servidor(endereco=ENDERECO, duracao=DURACAO_OPERACAO):
    torre = Torre(duracao)
    #inicia seu trabalhador
    servidor = grpc.server(ThreadPoolExecutor(max_workers=20), options=(("grpc.so_reuseport", 0),))
    rpc.add_ControleTrafegoServicer_to_server(torre, servidor)
    try:
        #configura o endereço de escuta sem criptografia TLS
        porta = servidor.add_insecure_port(endereco)
        servidor.start()
    except Exception:
        torre.encerrar()
        servidor.stop(0)
        raise
    return servidor, torre, porta


def main():
    servidor = torre = None
    try:
        servidor, torre, porta = criar_servidor()
        print(f"Servidor na porta {porta}. Inicie os clientes em outros terminais.", flush=True)
        Painel(torre).executar()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    except (RuntimeError, OSError, ValueError) as erro:
        print(f"Não foi possível iniciar o servidor: {erro}")
        return 1
    finally:
        if torre is not None:
            torre.encerrar()
        if servidor is not None:
            servidor.stop(grace=1).wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
