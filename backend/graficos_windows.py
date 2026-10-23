"""Primeiro recurso gráfico RS: diálogo Win32 modal com UTF-16 nativo."""
from compilador.erros import ErroCompilacao


def emitir_dialogo(g, titulo, mensagem, windows):
    """Emite a chamada MessageBoxW seguindo a ABI Windows x64.

    O backend existente reserva o shadow space de 32 bytes e alinha RSP
    nas fronteiras de chamada. Strings são dados UTF-16 estáticos no PE.
    """
    if not windows:
        raise ErroCompilacao('janela_mensagem está disponível apenas para Windows nesta versão.')
    textos = getattr(g, 'mensagens_graficas', None)
    if textos is None:
        textos = {}
        g.mensagens_graficas = textos
    indice = len(textos) // 2
    titulo_id = f'grafico_titulo_{indice}'
    corpo_id = f'grafico_mensagem_{indice}'
    textos[titulo_id] = titulo
    textos[corpo_id] = mensagem

    g.bytes(b'\x31\xC9')                     # xor ecx,ecx  (HWND = NULL)
    g.relativo(b'\x48\x8D\x15', corpo_id) # lea rdx,[rip+texto]
    g.relativo(b'\x4C\x8D\x05', titulo_id) # lea r8,[rip+titulo]
    g.bytes(b'\x45\x31\xC9')              # xor r9d,r9d (MB_OK)
    g.relativo(b'\xFF\x15', 'MessageBoxW')    # call [rip+IAT]
