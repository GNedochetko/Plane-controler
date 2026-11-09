# Simulador Distribuído de Controle de Tráfego Aéreo

Projeto acadêmico desenvolvido em Python, com comunicação gRPC e interfaces gráficas em Tkinter. Simula uma torre que coordena pousos e decolagens em uma única pista.

## Funcionamento

- O servidor recebe os pedidos e organiza uma fila por ordem de chegada.
- Uma aeronave utiliza a pista por vez. O painel mostra a fila, os acontecimentos e uma seta animada durante a operação.
- Cada cliente permite informar o IP do servidor, o identificador da aeronave e a operação desejada, acompanhando seu status.
- Após pousar, a interface oferece decolagem; após decolar, oferece pouso. Cada operação dura cinco segundos.

## Como executar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Inicie o servidor:

```powershell
python servidor.py
```

Em outro terminal, ative o ambiente e abra um cliente:

```powershell
.\.venv\Scripts\Activate.ps1
python cliente.py
```

Informe o IP do computador que executa o servidor. Para testar no mesmo computador, use `localhost`. A porta utilizada é `50051`. Abra outros clientes em terminais separados para observar a fila.

## Arquivos principais

- `servidor.py`: comunicação gRPC e controle da fila e da pista.
- `cliente.py`: interface da aeronave e envio das solicitações.
- `painel.py`: visualização da torre e animação da pista.
- `controle.proto`: contrato das mensagens e do serviço gRPC.
- `controle_pb2.py` e `controle_pb2_grpc.py`: arquivos gerados automaticamente a partir do contrato.
