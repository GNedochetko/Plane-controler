import tkinter as tk
from tkinter.scrolledtext import ScrolledText


class Painel:
    def __init__(self, torre):
        self.torre = torre
        self.raiz = tk.Tk()
        self.raiz.title("Torre de controle")
        self.raiz.geometry("780x530")
        self.raiz.minsize(620, 440)
        self.raiz.configure(bg="#f4f5f7")
        self.raiz.protocol("WM_DELETE_WINDOW", self.fechar)
        self.fechado = False
        self._ultima_fila = None
        self._ultimos_eventos = None

        tk.Label(self.raiz, text="Torre de controle", font=("Segoe UI", 18, "bold"), bg="#f4f5f7").pack(pady=(15, 4))
        self.situacao = tk.Label(self.raiz, text="Pista livre — aguardando aeronaves", font=("Segoe UI", 12), bg="#f4f5f7")
        self.situacao.pack(pady=(0, 8))

        self.pista = tk.Canvas(self.raiz, height=165, bg="#e1e9df", highlightthickness=0)
        self.pista.pack(fill="x", padx=16)
        self.pista.bind("<Configure>", self._desenhar_pista)

        inferior = tk.Frame(self.raiz, bg="#f4f5f7")
        inferior.pack(fill="both", expand=True, padx=16, pady=16)
        inferior.columnconfigure(0, weight=1)
        inferior.columnconfigure(1, weight=2)
        inferior.rowconfigure(1, weight=1)
        for coluna, titulo in ((0, "Fila de espera"), (1, "O que está acontecendo")):
            tk.Label(inferior, text=titulo, font=("Segoe UI", 11, "bold"), bg="#f4f5f7").grid(row=0, column=coluna, sticky="w", pady=(0, 6))
        self.fila = tk.Listbox(inferior, width=26, height=8, font=("Segoe UI", 11), relief="solid", borderwidth=1, activestyle="none")
        self.fila.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        self.eventos = ScrolledText(inferior, width=45, height=8, font=("Segoe UI", 10), wrap="word", relief="solid", borderwidth=1, state="disabled")
        self.eventos.grid(row=1, column=1, sticky="nsew")
        self._agendamento = self.raiz.after(30, self.atualizar)

    def _desenhar_pista(self, evento=None):
        largura = self.pista.winfo_width()
        self.pista.delete("all")
        self.pista.create_rectangle(25, 45, largura - 25, 125, fill="#46515c", outline="")
        self.pista.create_line(60, 85, largura - 60, 85, fill="white", width=3, dash=(24, 20))
        for x in (38, largura - 53):
            for y in (55, 101):
                self.pista.create_rectangle(x, y, x + 15, y + 14, fill="white", outline="")
        self.seta = self.pista.create_polygon(0, 0, 0, 0, 0, 0, tags="aviao", state="hidden")

    def atualizar(self):
        dados = self.torre.fotografia()
        voo = dados["atual"]
        if voo is None:
            self.situacao.configure(text="Pista livre — aguardando aeronaves", fg="#27623c")
            self.pista.itemconfigure("aviao", state="hidden")
        else:
            pouso = voo["operacao"] == "pouso"
            self.situacao.configure(text=f"{voo['id']} — {'pousando' if pouso else 'decolando'}", fg="#1f527a")
            largura = self.pista.winfo_width()
            progresso = voo["progresso"]
            inicio, fim = (largura - 65, 65) if pouso else (65, largura - 65)
            x = inicio + (fim - inicio) * progresso
            direcao = -1 if pouso else 1
            self.pista.coords("aviao", x + direcao * 22, 85, x - direcao * 18, 68, x - direcao * 9, 85, x - direcao * 18, 102)
            self.pista.itemconfigure("aviao", state="normal", fill="#82d3f7" if pouso else "#ffc36b", outline="#1e2933", width=2)

        if dados["fila"] != self._ultima_fila:
            self._ultima_fila = dados["fila"]
            self.fila.delete(0, "end")
            for posicao, (identificador, operacao) in enumerate(dados["fila"], 1):
                self.fila.insert("end", f"{posicao}. {identificador} — {operacao}")
            if not dados["fila"]:
                self.fila.insert("end", "(fila vazia)")
        if dados["eventos"] != self._ultimos_eventos:
            self._ultimos_eventos = dados["eventos"]
            self.eventos.configure(state="normal")
            self.eventos.delete("1.0", "end")
            self.eventos.insert("end", "\n".join(dados["eventos"]))
            self.eventos.see("end")
            self.eventos.configure(state="disabled")
        self._agendamento = self.raiz.after(30, self.atualizar)

    def fechar(self):
        if not self.fechado:
            self.fechado = True
            self.raiz.after_cancel(self._agendamento)
            self.raiz.destroy()

    def executar(self):
        try:
            self.raiz.mainloop()
        finally:
            self.fechar()
