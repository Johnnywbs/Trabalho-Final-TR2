class RateBasedABR:
    def __init__(self, manifest, fator_seguranca=0.8, tamanho_janela=3):
        """
        Inicializa o algoritmo ABR.
        :param manifest: O dicionário do manifest carregado do servidor.
        :param fator_seguranca: Multiplicador para jogar seguro com a banda (padrão 80%).
        :param tamanho_janela: Quantos segmentos lembrar para calcular a média recente.
        """
        self.fator_seguranca = fator_seguranca
        self.tamanho_janela = tamanho_janela
        self.historico_vazao = [] # Guarda as últimas medições em kbps
        
        # Extrai as qualidades do manifest e garante que estão ordenadas do MAIOR para o MENOR bitrate.
        # Isso facilita a busca (vamos testando do mais pesado pro mais leve).
        self.qualidades = sorted(
            manifest["representations"], 
            key=lambda q: q["bitrate_kbps"], 
            reverse=True
        )

    def registrar_vazao(self, vazao_kbps):
        """
        Guarda a nova medição. Se passar do limite da janela, joga a mais velha fora.
        """
        self.historico_vazao.append(vazao_kbps)
        if len(self.historico_vazao) > self.tamanho_janela:
            self.historico_vazao.pop(0) # Remove o primeiro item (o mais antigo)

    def obter_proxima_qualidade(self):
        """
        Decide qual qualidade baixar no próximo segmento.
        """
        # Regra do Slow Start (Início Lento): 
        # Se não temos histórico (é o 1º segmento), retorna a pior qualidade para testar a rede rápido.
        if not self.historico_vazao:
            pior_qualidade = self.qualidades[-1] # O último da lista ordenada
            print(f"[ABR] Sem histórico. Iniciando na qualidade mais baixa: {pior_qualidade['quality']}")
            return pior_qualidade["quality"]

        # 1. Calcula a vazão média recente
        media_vazao = sum(self.historico_vazao) / len(self.historico_vazao)
        
        # 2. Aplica o fator de segurança
        vazao_segura = media_vazao * self.fator_seguranca

        print(f"[ABR] Média recente: {media_vazao:.2f} kbps | Vazão Segura (estimada): {vazao_segura:.2f} kbps")

        # 3. Procura a maior qualidade que cabe na vazão segura
        for q in self.qualidades:
            if q["bitrate_kbps"] <= vazao_segura:
                print(f"[ABR] Qualidade escolhida: {q['quality']} (Requer {q['bitrate_kbps']} kbps)")
                return q["quality"]

        # 4. Caso extremo: a internet está tão ruim que nem a pior qualidade cabe na vazão segura.
        # Nesse caso, não temos escolha a não ser forçar a pior qualidade e torcer para o buffer aguentar.
        pior_qualidade = self.qualidades[-1]
        print(f"[ABR] Internet crítica! Forçando a qualidade mínima: {pior_qualidade['quality']}")
        return pior_qualidade["quality"]