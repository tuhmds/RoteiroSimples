# Referencia congelada da RS 0.42O, commit e79d41c. Somente para verificacao diferencial.
import struct

def compactar_antes(self):
        """Relaxa rel32->rel8 em ponto fixo, corrigindo TODOS os offsets.

        Nao encurta chamadas, referencias RIP a dados, nem saltos das
        rotinas auxiliares. Essas referencias tambem sao remapeadas.
        """
        import bisect
        candidatos = sorted(self._candidatos_curto)
        if not candidatos:
            return 0
        antigos = bytes(self.codigo)
        selecionados = set()
        # Cada troca reduz em 3 ou 4 bytes. Reducoes tornam outros saltos
        # pelo menos tao proximos; portanto a relaxacao e monotona.
        while True:
            alterou = False
            for inicio, tamanho, alvo, opcode in candidatos:
                if inicio in selecionados:
                    continue
                if alvo not in self.rotulos:
                    raise ValueError(f'Rotulo local de salto curto desconhecido: {alvo}')
                hipotese = selecionados | {inicio}
                # Recalcular explicitamente com a hipotese; usa posições
                # ORIGINAIS e desconta apenas saltos que terminam antes.
                def ajustado(posicao):
                    return posicao - sum(tam - 2 for pos, tam, _, _ in candidatos
                                         if pos in hipotese and pos + tam <= posicao)
                deslocamento = ajustado(self.rotulos[alvo]) - (ajustado(inicio) + 2)
                if -128 <= deslocamento <= 127:
                    selecionados.add(inicio)
                    alterou = True
            if not alterou:
                break
        if not selecionados:
            return 0
        candidatos_ativos = [(pos, tam, alvo, opcode) for pos, tam, alvo, opcode in candidatos if pos in selecionados]
        finais = [pos + tam for pos, tam, _, _ in candidatos_ativos]
        acumulado = [0]
        for _, tam, _, _ in candidatos_ativos:
            acumulado.append(acumulado[-1] + tam - 2)
        def mapear(posicao):
            return posicao - acumulado[bisect.bisect_right(finais, posicao)]
        saida = bytearray()
        cursor = 0
        pendentes_removidas = set()
        for pos, tam, alvo, opcode in candidatos_ativos:
            saida += antigos[cursor:pos]
            distancia = mapear(self.rotulos[alvo]) - (mapear(pos) + 2)
            if not -128 <= distancia <= 127:
                raise ValueError('Salto curto fora da faixa apos compactacao.')
            saida += bytes((opcode,)) + struct.pack('<b', distancia)
            pendentes_removidas.add(pos + tam - 4)
            cursor = pos + tam
        saida += antigos[cursor:]
        self.codigo = saida
        self.rotulos = {nome: mapear(pos) for nome, pos in self.rotulos.items()}
        self.pendencias = [(mapear(pos), nome) for pos, nome in self.pendencias
                           if pos not in pendentes_removidas]
        self.saltos_compactados = len(selecionados)
        self._candidatos_curto.clear()
        return self.saltos_compactados
