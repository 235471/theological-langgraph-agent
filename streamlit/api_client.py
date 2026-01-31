import time


class MockApiClient:
    def get_verses(self, book_abbrev, chapter):
        """
        Simulates GET /bible/books/{abbrev}/{chapter}/verses
        Returns a list of dicts: {'number': int, 'text': str}
        """
        # Mock delay
        time.sleep(0.3)

        # Mock Logic: Just generate some dummy verses
        verses = []
        verse_count = 10  # Arbitrary number for demo

        # Adjust count for specific famous chapters if needed, but generic is fine for MVP
        if book_abbrev == "Sl" and chapter == 23:
            verses_texts = [
                "O Senhor é o meu pastor, nada me faltará.",
                "Deitar-me faz em verdes pastos, guia-me mansamente a águas tranquilas.",
                "Refrigera a minha alma; guia-me pelas veredas da justiça, por amor do seu nome.",
                "Ainda que eu andasse pelo vale da sombra da morte, não temeria mal algum, porque tu estás comigo; a tua vara e o teu cajado me consolam.",
                "Preparas uma mesa perante mim na presença dos meus inimigos, unges a minha cabeça com óleo, o meu cálice transborda.",
                "Certamente que a bondade e a misericórdia me seguirão todos os dias da minha vida; e habitarei na casa do Senhor por longos dias.",
            ]
            for i, text in enumerate(verses_texts):
                verses.append({"number": i + 1, "text": text})
        else:
            for i in range(1, verse_count + 1):
                verses.append(
                    {
                        "number": i,
                        "text": f"Este é o texto simulado para o versículo {i} do capítulo {chapter} de {book_abbrev}.",
                    }
                )

        return verses

    def analyze(self, payload):
        """
        Simulates POST /analyze
        Payload: {
            "book": str,
            "chapter": int,
            "verses": List[int],
            "selected_modules": List[str]
        }
        """
        # Mock delay
        time.sleep(1.5)

        modules = payload.get("selected_modules", [])
        book = payload.get("book")
        chapter = payload.get("chapter")
        verses = payload.get("verses")

        # Generate Markdown response
        md_output = f"""
# Análise Teológica: {book.upper()} {chapter}:{verses}

**Módulos Executados:** {', '.join(modules)}

---
"""

        if "panorama" in modules or not modules:
            md_output += f"""
## 1. Panorama
O capítulo {chapter} do livro de {book} situa-se em um contexto histórico rico. 
A narrativa aqui foca na providência divina e na resposta humana diante das circunstâncias da vida.
Observamos temas centrais como *confiança*, *redenção* e *aliança*.
"""

        if "exegese" in modules or not modules:
            md_output += f"""
## 2. Exegese
Analisando os versículos selecionados ({verses}):

*   **Versículo 1**: A palavra original para "Pastor" indica não apenas cuidado, mas governança real.
*   **Conexões Linguísticas**: Há paralelos claros com textos do antigo oriente próximo, porém com a distinção do monoteísmo ético.
*   **Estrutura Literária**: O texto apresenta um quiasmo central, enfatizando a presença divina no centro da experiência humana.
"""

        if "teologia" in modules or not modules:
            md_output += f"""
## 3. Teologia Sistemática
Doutrinariamente, este trecho reforça:

1.  **A Imutabilidade de Deus**: Sua promessa de presença é constante.
2.  **Soteriologia**: A salvação é apresentada como uma iniciativa divina ("Ele me guia").
3.  **Escatologia**: A "casa do Senhor" aponta para uma esperança futura e eterna.
"""

        md_output += "\n\n*Análise gerada pelo Agente LangGraph (Mock).*"

        return md_output


# Singleton instance for easy import
api_client = MockApiClient()
