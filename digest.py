import os
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

import feedparser
from google import genai

# ---------- À PERSONNALISER ----------
# Vérifie le nom exact du modèle gratuit dans Google AI Studio
MODEL = "gemini-3.8-flash"

MAX_ARTICLES_PAR_THEME = 15   # articles envoyés au LLM par thème
ITEMS_PAR_THEME = 3           # items dans le digest final
HEURES = 36                   # fenêtre de fraîcheur des articles

THEMES = {
    "Politique française": [
        "https://www.lemonde.fr/politique/rss_full.xml",
        "https://www.lefigaro.fr/rss/figaro_politique.xml",
        "https://www.francetvinfo.fr/politique.rss",
    ],
    "Politique mondiale": [
        "https://www.theguardian.com/world/rss",
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://www.lemonde.fr/international/rss_full.xml",
    ],
    "Économie (France et monde)": [
        "https://www.lemonde.fr/economie/rss_full.xml",
        "https://www.francetvinfo.fr/economie.rss",
        "https://www.theguardian.com/business/rss",
        "http://feeds.bbci.co.uk/news/business/rss.xml",
    ],
    "Science": [
        "https://www.science.org/rss/news_current.xml",
        "https://www.nature.com/nature.rss",
        "https://theconversation.com/fr/articles.atom",
    ],
}
# --------------------------------------


def recuperer_articles(urls):
    limite = datetime.now(timezone.utc) - timedelta(hours=HEURES)
    articles = []
    for url in urls:
        try:
            flux = feedparser.parse(url)
            for e in flux.entries:
                date = e.get("published_parsed") or e.get("updated_parsed")
                if date:
                    d = datetime.fromtimestamp(time.mktime(date), timezone.utc)
                    if d < limite:
                        continue
                articles.append(
                    {
                        "titre": e.get("title", ""),
                        "resume": (e.get("summary", "") or "")[:400],
                        "lien": e.get("link", ""),
                        "source": flux.feed.get("title", url),
                    }
                )
        except Exception as ex:
            print(f"Flux ignoré ({url}) : {ex}")
    return articles[:MAX_ARTICLES_PAR_THEME]


def construire_prompt(donnees):
    blocs = []
    for theme, articles in donnees.items():
        lignes = [
            f"- [{a['source']}] {a['titre']} | {a['resume']} | {a['lien']}"
            for a in articles
        ]
        blocs.append(f"## {theme}\n" + "\n".join(lignes))
    matiere = "\n\n".join(blocs)

    return f"""Tu rédiges un digest d'actualité quotidien en français, pour une lectrice
curieuse qui veut pouvoir en parler à l'oral. Voici les articles du jour, par thème.

Consignes :
- Pour chaque thème : maximum {ITEMS_PAR_THEME} items, les plus importants.
  Regroupe les articles qui parlent du même sujet.
- Chaque item : un titre court, 2 phrases de contexte factuel, et le lien.
- Base-toi uniquement sur les informations fournies. N'invente rien.
  Si l'extrait est trop mince, dis-le et donne juste le titre et le lien.
- Si plusieurs sources divergent sur un sujet, signale-le.
- Termine par une section « À lire en profondeur » : UN seul article du jour
  qui mérite un vrai temps de lecture, avec le lien et pourquoi.
- Termine par une section « Pour y réfléchir » : UNE question ouverte
  liée à l'actualité du jour.
- Texte brut, sans markdown lourd.

Articles :

{matiere}
"""


def envoyer_email(corps):
    adresse = os.environ["GMAIL_ADDRESS"]
    mdp = os.environ["GMAIL_APP_PASSWORD"]
    msg = MIMEText(corps, "plain", "utf-8")
    msg["Subject"] = f"Digest actu du {datetime.now().strftime('%d/%m/%Y')}"
    msg["From"] = adresse
    msg["To"] = adresse
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(adresse, mdp)
        s.send_message(msg)


def main():
    donnees = {t: recuperer_articles(urls) for t, urls in THEMES.items()}
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    reponse = client.models.generate_content(
        model=MODEL, contents=construire_prompt(donnees)
    )
    envoyer_email(reponse.text)
    print("Digest envoyé.")


if __name__ == "__main__":
    main()
