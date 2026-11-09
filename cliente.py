from queue import Empty, Queue
from threading import Event, Thread
import tkinter as tk
from tkinter import ttk

import grpc

import controle_pb2 as pb
import controle_pb2_grpc as rpc


PORTA = 50051


class Cliente:
    def __init__(self):
        self.endereco = None
        self.raiz = tk.Tk()
        self.raiz.title("Servidor")
        self.raiz.geometry("430x230")
        self.raiz.resizable(False, False)
        self.raiz.protocol("WM_DELETE_WINDOW", self.fechar)
        self.aeronave_id = tk.StringVar(self.raiz)
        self.operacao = tk.StringVar(self.raiz, value="pouso")
        self.situacao = tk.StringVar(self.raiz, value="Escolha a primeira operação.")
        self.status = tk.StringVar(self.raiz, value="Aguardando solicitação.")
        self.fechado = False
        self._id_fixo = None
        self._chamada = None
        self._parar = Event()
        self._resultados = Queue()

        self.ip_servidor = tk.StringVar(self.raiz)
        self.aviso_ip = tk.StringVar(self.raiz)
        self.tela_servidor = ttk.Frame(self.raiz, padding=24)
        self.tela_servidor.pack(fill="both", expand=True)
        ttk.Label(self.tela_servidor, text="Servidor", font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(0, 14))
        ttk.Label(self.tela_servidor, text="IP do servidor (ou localhost neste computador)").pack(anchor="w")
        self.entrada_ip = ttk.Entry(self.tela_servidor, textvariable=self.ip_servidor)
        self.entrada_ip.pack(fill="x", pady=(3, 12))
        self.entrada_ip.bind("<Return>", lambda evento: self.confirmar_servidor())
        ttk.Button(self.tela_servidor, text="Continuar", command=self.confirmar_servidor).pack(fill="x")
        ttk.Label(self.tela_servidor, textvariable=self.aviso_ip).pack(anchor="w", pady=(8, 0))
        self.entrada_ip.focus_set()
        self._agendamento = self.raiz.after(100, self._receber)

    def confirmar_servidor(self):
        ip = self.ip_servidor.get().strip()
        if not ip:
            self.aviso_ip.set("Informe o IP do servidor.")
            return
        self.endereco = f"{ip}:{PORTA}"
        self.tela_servidor.destroy()
        self.raiz.title("Aeronave")
        self.raiz.geometry("430x390")
        corpo = ttk.Frame(self.raiz, padding=24)
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text="Aeronave", font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Label(corpo, text=f"Servidor: {ip}").pack(anchor="w", pady=(0, 10))
        ttk.Label(corpo, text="Identificador").pack(anchor="w")
        self.identificador = ttk.Entry(corpo, textvariable=self.aeronave_id)
        self.identificador.pack(fill="x", pady=(3, 10))
        ttk.Label(corpo, text="Operação").pack(anchor="w")
        self.escolha = ttk.Combobox(corpo, textvariable=self.operacao, values=("pouso", "decolagem"), state="readonly")
        self.escolha.pack(fill="x", pady=(3, 12))
        self.botao = ttk.Button(corpo, text="Solicitar operação", command=self.solicitar)
        self.botao.pack(fill="x")
        ttk.Label(corpo, textvariable=self.situacao, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(12, 4))
        ttk.Label(corpo, textvariable=self.status, wraplength=380).pack(anchor="w")
        self.identificador.focus_set()

    def solicitar(self):
        identificador = self.aeronave_id.get().strip()
        operacao = self.operacao.get()
        if not identificador:
            self.status.set("Informe o identificador da aeronave.")
            return
        self.aeronave_id.set(identificador)
        self._operacao_enviada = operacao
        self.identificador.configure(state="disabled")
        self.escolha.configure(state="disabled")
        self.botao.configure(state="disabled")
        self.status.set("Conectando à torre...")
        Thread(target=self._enviar, args=(identificador, operacao), daemon=True).start()

    def _enviar(self, identificador, operacao):
        try:
            # abre o canal e aguarda a conexão.
            with grpc.insecure_channel(self.endereco) as canal:
                conexao = grpc.channel_ready_future(canal)
                try:
                    conexao.result(timeout=5)
                except grpc.FutureTimeoutError:
                    self._resultados.put(("erro", "Sem conexão. Inicie o servidor primeiro."))
                    return
                finally:
                    conexao.cancel()
                if self._parar.is_set():
                    return
                # O Stub permite chamar o método remoto da torre
                torre = rpc.ControleTrafegoStub(canal)
                self._chamada = torre.SolicitarOperacao(pb.Solicitacao(aeronave_id=identificador, operacao=operacao))
                if self._parar.is_set():
                    self._chamada.cancel()
                    return
                concluida = False
                for atualizacao in self._chamada:
                    self._resultados.put(("estado", atualizacao))
                    concluida = concluida or atualizacao.estado == "finalizada"
                if not concluida and not self._parar.is_set():
                    self._resultados.put(("erro", "A conexão terminou antes da confirmação da operação."))
        except grpc.RpcError as erro:
            self._resultados.put(("erro", erro.details() or "A conexão com a torre foi interrompida."))
        finally:
            self._chamada = None
            self._resultados.put(("fim", None))

    def _receber(self):
        # transforma os resultados em alterações na interface
        try:
            while True:
                tipo, dados = self._resultados.get_nowait()
                if tipo == "erro":
                    self.status.set(dados)
                elif tipo == "estado":
                    self._id_fixo = self.aeronave_id.get()
                    self.raiz.title(f"Aeronave — {self._id_fixo}")
                    self.status.set(dados.mensagem)
                    if dados.estado == "aguardando":
                        self.situacao.set("Na fila de espera")
                    elif dados.estado == "em_operacao":
                        self.situacao.set("Pousando..." if self._operacao_enviada == "pouso" else "Decolando...")
                    elif dados.estado == "finalizada":
                        self.situacao.set("Em solo" if self._operacao_enviada == "pouso" else "No ar")
                        proxima = "decolagem" if self._operacao_enviada == "pouso" else "pouso"
                        self.escolha.configure(values=(proxima,))
                        self.operacao.set(proxima)
                elif tipo == "fim":
                    self.escolha.configure(state="readonly")
                    self.botao.configure(state="normal")
                    if self._id_fixo is None:
                        self.identificador.configure(state="normal")
        except Empty:
            pass
        # O método agenda sua próxima execução
        self._agendamento = self.raiz.after(100, self._receber)

    def fechar(self):
        if not self.fechado:
            self.fechado = True
            self._parar.set()
            if self._chamada is not None:
                self._chamada.cancel()
            self.raiz.after_cancel(self._agendamento)
            self.raiz.destroy()

    def executar(self):
        try:
            self.raiz.mainloop()
        finally:
            self.fechar()


if __name__ == "__main__":
    try:
        Cliente().executar()
    except KeyboardInterrupt:
        pass
