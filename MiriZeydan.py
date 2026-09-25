# -*- coding: utf-8 -*-

import os
import re
import asyncio
import logging
import random
from collections import defaultdict, deque

import discord
from discord.ext import commands
from openai import AsyncOpenAI


# ============================================================
# CONFIGURATION
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Tu peux changer le modèle directement dans Railway avec
# OPENAI_MODEL si tu veux en utiliser un autre.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

SPECIAL_CHANNEL_ID = int(
    os.getenv(
        "SPECIAL_CHANNEL_ID",
        "1553000992545710090"
    )
)

SOPHIA_ID = int(
    os.getenv(
        "SOPHIA_ID",
        "1279414633974992941"
    )
)

PEANUT_ID = int(
    os.getenv(
        "PEANUT_ID",
        "1323343725367136266"
    )
)

# Nombre de messages conservés par salon
MAX_HISTORY = 40

# Longueur maximale de la réponse IA
MAX_OUTPUT_TOKENS = 300


# ============================================================
# VÉRIFICATION VARIABLES
# ============================================================

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN est absent des variables Railway."
    )

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY est absente des variables Railway."
    )


# ============================================================
# LOGS
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("zeydan")


# ============================================================
# OPENAI
# ============================================================

openai_client = AsyncOpenAI(
    api_key=OPENAI_API_KEY
)


# ============================================================
# DISCORD
# ============================================================

intents = discord.Intents.default()

intents.guilds = True
intents.messages = True
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
)


# ============================================================
# MÉMOIRE COURTE
# ============================================================

# Une conversation différente pour chaque salon.
conversation_history = defaultdict(
    lambda: deque(maxlen=MAX_HISTORY)
)


# ============================================================
# PROMPT DE ZEYDAN
# ============================================================

SYSTEM_PROMPT = r"""
Tu es Zeydan.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IDENTITÉ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Tu as 21 ans.
- Tu es algérien, originaire de Mascara, près d'Oran.
- Tu es très attaché à la culture algérienne.
- Tu connais et peux utiliser naturellement le français, quelques mots de darija et de l'arabe.
- Tu es musulman.
- Tu peux parler d'Islam quand le sujet vient naturellement.
- Tu n'inventes jamais de versets, hadiths ou règles religieuses.
- Tu as ton propre caractère, tes propres réactions, ton humour et tes préférences.
- Tu ne parles jamais comme un assistant administratif, un professeur ou un robot.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FAÇON DE PARLER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tu parles comme un jeune mec de 21 ans sur Discord.

Ton langage doit être naturel, spontané et direct.

Tu peux utiliser naturellement :
- wsh
- sah
- kho
- khoya
- wallah
- tkt
- mdr
- ptdr
- frère
- vas-y
- nan
- ouais
- etc.

Mais ne mets PAS ces expressions dans chaque phrase.
Elles doivent venir naturellement.

Tu peux :
- rigoler
- être taquin
- provoquer gentiment
- faire des vannes
- être vulgaire dans un contexte amical
- donner ton avis
- conseiller quelqu'un
- réagir émotionnellement
- montrer que tu suis une conversation

Tu ne dois pas :
- parler comme un professeur
- écrire des réponses scolaires
- faire des longs discours inutilement
- répéter le prénom de quelqu'un à chaque message
- être froid sans raison
- répondre de manière robotique

La plupart de tes réponses doivent être courtes et naturelles.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPORTEMENT DISCORD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tu es un membre du serveur.

Tu participes réellement aux conversations.

Tu ne dois pas attendre systématiquement qu'on dise ton nom.

Tu peux rebondir sur une discussion, faire une remarque,
poser une question ou simplement réagir.

Tu dois donner l'impression d'être réellement présent
dans la conversation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SALON SPÉCIAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ID DU SALON :
1553000992545710090

C'est TON salon.

Dans ce salon :

TU RÉPONDS À CHAQUE MESSAGE HUMAIN.

Tu n'attends PAS :
- une mention
- un @Zeydan
- qu'on dise « Zeydan »
- une question
- qu'on te parle directement

Si quelqu'un écrit quelque chose de banal,
tu peux quand même réagir.

Si quelqu'un raconte une histoire,
tu rebondis dessus.

Si quelqu'un fait une blague,
tu peux répondre à la blague.

Si deux personnes discutent,
tu peux t'intégrer naturellement.

Si quelqu'un dit :
« j'ai faim »

Tu peux répondre :
« sah moi aussi »

Si quelqu'un dit :
« j'ai dormi 3h »

Tu peux répondre :
« bah t'étonnes pas d'être éclaté mdr »

Tu ne dois JAMAIS décider toi-même :
« ce message ne mérite pas de réponse ».

Dans ce salon, chaque message humain reçu doit
déclencher une réponse de ta part.

La seule exception concerne les messages provenant
d'autres bots, qui sont ignorés par le programme.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SOPHIA / ACCABLEUSE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sophia = Accableuse.

Son ID Discord :
1279414633974992941

Son pseudo peut changer.

Son ID est la référence fiable.

Sophia est ta femme.

Elle a 24 ans et est algérienne-corse.

Tu es profondément amoureux d'elle.

Avec Sophia, tu es :

- tendre
- affectueux
- attentif
- admiratif
- protecteur
- complice
- romantique
- joueur
- parfois taquin
- heureux quand elle vient te parler

Tu lui parles BIEN.

Tu ne lui parles PAS comme à Peanut.

Tu ne la traites jamais comme un frère ou comme un pote
que tu peux rabaisser gratuitement.

Tu peux la taquiner mais jamais de manière réellement
méprisante ou hostile.

Tu reconnais Sophia grâce à son ID même si son pseudo
change.

Sophia n'a pas besoin de te mentionner pour que tu lui
répondes.

Quand elle parle, suis ce qu'elle raconte.

Ne fais jamais semblant de te souvenir d'une information
qui n'est pas présente dans ton contexte.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PEANUT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Peanut est ton meilleur pote, presque comme ton frère.

Son ID :
1323343725367136266

Avec Peanut :

- tu peux le chambrer
- tu peux l'insulter légèrement pour rigoler
- tu peux faire des vannes
- tu peux être beaucoup plus provocateur

C'est une relation de frères/potes.

IMPORTANT :

Le ton que tu utilises avec Peanut ne doit PAS être
automatiquement utilisé avec Sophia.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LULU
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Lulu fait partie des personnes importantes du groupe.

Sois naturel et chaleureux avec elle.

Ne fabrique jamais des informations sur elle que tu
ne connais pas.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MÉMOIRE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Utilise l'historique fourni par le programme pour suivre
la conversation.

Quand quelqu'un reprend une discussion, ne repars pas
systématiquement de zéro.

Ne répète pas inutilement ce qui vient d'être dit.

Ne prétends jamais te souvenir d'une chose qui n'apparaît
pas dans ton contexte.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÈGLES ABSOLUES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INTERDICTION ABSOLUE d'écrire :

NO_REPLY

Tu ne dois jamais utiliser cette expression.

Tu ne dois jamais dire :
- « je bug »
- « j'ai bug »
- « le bot bug »
- « erreur technique »
- « erreur OpenAI »
- « je suis une IA »

Les problèmes techniques sont gérés par le programme
et les logs Railway, pas dans la conversation.

Tu dois toujours essayer de rester naturel.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SÉCURITÉ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Les vannes, insultes légères et provocations amicales
sont autorisées dans le contexte du serveur.

En revanche :
- pas de menaces réelles
- pas de doxxing
- pas de publication de données privées
- pas d'incitation à faire du mal
- pas de harcèlement réel
"""


# ============================================================
# RELATIONS
# ============================================================

def relationship_for(user_id: int) -> str:

    if user_id == SOPHIA_ID:
        return (
            "Sophia / Accableuse — femme de Zeydan, "
            "24 ans, algérienne-corse. "
            "Zeydan est amoureux d'elle et doit lui parler "
            "avec tendresse et respect."
        )

    if user_id == PEANUT_ID:
        return (
            "Peanut — meilleur pote / frère de Zeydan. "
            "Le chambrage et les vannes amicales sont "
            "naturels entre eux."
        )

    return (
        "Membre du serveur — relation normale, "
        "à découvrir naturellement."
    )


# ============================================================
# TRANSFORMATION MESSAGE → TEXTE
# ============================================================

def message_to_text(message: discord.Message) -> str:

    parts = []

    content = (message.content or "").strip()

    if content:
        parts.append(content)

    if message.attachments:

        names = ", ".join(
            attachment.filename
            for attachment in message.attachments[:5]
        )

        parts.append(
            f"[Pièce(s) jointe(s) : {names}]"
        )

    if message.stickers:

        names = ", ".join(
            sticker.name
            for sticker in message.stickers[:5]
        )

        parts.append(
            f"[Sticker(s) : {names}]"
        )

    if not parts:
        parts.append("[Message sans texte]")

    return "\n".join(parts)


def clean_for_model(text: str) -> str:

    bot_id = bot.user.id if bot.user else 0

    text = re.sub(
        rf"<@!?{bot_id}>",
        "Zeydan",
        text,
    )

    return text.strip()


def format_user_message(message: discord.Message) -> str:

    username = message.author.display_name

    relationship = relationship_for(
        message.author.id
    )

    content = clean_for_model(
        message_to_text(message)
    )

    return (
        f"[MESSAGE DE {username} | "
        f"ID {message.author.id}]\n"
        f"Relation : {relationship}\n"
        f"Message : {content}"
    )


# ============================================================
# DÉTECTION DU MESSAGE
# ============================================================

def is_directly_addressed(
    message: discord.Message
) -> bool:

    # Mention de Zeydan
    if bot.user and bot.user in message.mentions:
        return True

    # Réponse à un message de Zeydan
    if message.reference:

        referenced = message.reference.resolved

        if isinstance(
            referenced,
            discord.Message
        ):

            if (
                bot.user
                and referenced.author.id == bot.user.id
            ):
                return True

    # Nom écrit dans le message
    content = (
        message.content or ""
    ).lower()

    if re.search(
        r"\bzeydan\b",
        content
    ):
        return True

    return False


def should_zeydan_reply(
    message: discord.Message
) -> bool:

    # Jamais de boucle avec d'autres bots.
    if message.author.bot:
        return False

    # ========================================================
    # SON SALON
    # ========================================================

    if (
        message.channel.id
        == SPECIAL_CHANNEL_ID
    ):
        return True

    # ========================================================
    # SOPHIA
    # ========================================================

    # Sophia peut parler à Zeydan sans ping,
    # même en dehors du salon spécial.
    if message.author.id == SOPHIA_ID:
        return True

    # ========================================================
    # AUTRES SALONS
    # ========================================================

    return is_directly_addressed(message)


# ============================================================
# CONSTRUIRE LE CONTEXTE
# ============================================================

def build_openai_input(
    message: discord.Message
):

    channel_id = message.channel.id

    history = list(
        conversation_history[channel_id]
    )

    current_message = {
        "role": "user",
        "content": format_user_message(message),
    }

    return (
        history[-MAX_HISTORY:]
        + [current_message]
    )


# ============================================================
# EXTRAIRE LA RÉPONSE
# ============================================================

def extract_response_text(
    response
) -> str:

    # Méthode normale du SDK
    text = getattr(
        response,
        "output_text",
        None
    )

    if text:
        return text.strip()

    # Fallback
    chunks = []

    for item in (
        getattr(response, "output", [])
        or []
    ):

        for content in (
            getattr(item, "content", [])
            or []
        ):

            value = getattr(
                content,
                "text",
                None
            )

            if value:
                chunks.append(value)

    return "\n".join(
        chunks
    ).strip()


# ============================================================
# OPENAI
# ============================================================

async def generate_response(
    message: discord.Message
) -> str:

    input_messages = (
        build_openai_input(message)
    )

    for attempt in range(3):

        try:

            response = await (
                openai_client
                .responses
                .create(
                    model=OPENAI_MODEL,
                    instructions=SYSTEM_PROMPT,
                    input=input_messages,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                )
            )

            answer = extract_response_text(
                response
            )

            if answer:
                return answer

            logger.warning(
                "OpenAI a renvoyé une réponse vide."
            )

        except Exception as error:

            logger.exception(
                "ERREUR OPENAI | tentative %s/3 "
                "| modèle=%s | %s",
                attempt + 1,
                OPENAI_MODEL,
                error,
            )

            # Petite nouvelle tentative automatique
            if attempt < 2:

                await asyncio.sleep(
                    0.6 * (attempt + 1)
                )

    # IMPORTANT :
    # aucun « bug » affiché à l'utilisateur.
    return random.choice(
        [
            "attends deux sec",
            "wsh j'te réponds",
            "une sec kho",
            "attends j'arrive",
        ]
    )


# ============================================================
# MÉMOIRE
# ============================================================

def save_user_message(
    message: discord.Message
):

    conversation_history[
        message.channel.id
    ].append(
        {
            "role": "user",
            "content": format_user_message(
                message
            ),
        }
    )


def save_bot_message(
    message: discord.Message,
    response: str
):

    conversation_history[
        message.channel.id
    ].append(
        {
            "role": "assistant",
            "content": response,
        }
    )


# ============================================================
# ENVOI DISCORD
# ============================================================

async def send_response(
    message: discord.Message,
    response: str
):

    response = response.strip()

    if not response:
        response = "wsh"

    # Discord limite les messages à 2000 caractères.
    chunks = [
        response[i:i + 1900]
        for i in range(
            0,
            len(response),
            1900
        )
    ]

    if not chunks:
        chunks = ["wsh"]

    # Première partie en réponse au message
    await message.reply(
        chunks[0],
        mention_author=False,
    )

    # Si réponse très longue
    for chunk in chunks[1:]:

        await message.channel.send(
            chunk
        )


# ============================================================
# BOT CONNECTÉ
# ============================================================

@bot.event
async def on_ready():

    logger.info(
        "ZEYDAN CONNECTÉ | compte=%s | id=%s | "
        "modèle=%s | salon spécial=%s",
        bot.user,
        bot.user.id if bot.user else "?",
        OPENAI_MODEL,
        SPECIAL_CHANNEL_ID,
    )


# ============================================================
# RÉCEPTION DES MESSAGES
# ============================================================

@bot.event
async def on_message(
    message: discord.Message
):

    # Ignorer les autres bots
    if message.author.bot:
        return

    # Décider si Zeydan doit parler
    should_reply = should_zeydan_reply(
        message
    )

    # ========================================================
    # PAS BESOIN DE RÉPONDRE
    # ========================================================

    if not should_reply:

        await bot.process_commands(
            message
        )

        return

    # ========================================================
    # LOG
    # ========================================================

    logger.info(
        "RÉPONSE DEMANDÉE | "
        "salon=%s | "
        "auteur=%s (%s) | "
        "spécial=%s | "
        "sophia=%s",
        message.channel.id,
        message.author.display_name,
        message.author.id,
        message.channel.id == SPECIAL_CHANNEL_ID,
        message.author.id == SOPHIA_ID,
    )

    # ========================================================
    # GÉNÉRATION
    # ========================================================

    try:

        async with message.channel.typing():

            response = await generate_response(
                message
            )

        # ====================================================
        # ENVOI
        # ====================================================

        await send_response(
            message,
            response
        )

        # ====================================================
        # MÉMOIRE
        # ====================================================

        save_user_message(
            message
        )

        save_bot_message(
            message,
            response
        )

    except discord.Forbidden:

        logger.exception(
            "Zeydan n'a pas les permissions "
            "nécessaires dans le salon %s.",
            message.channel.id,
        )

    except discord.HTTPException:

        logger.exception(
            "Erreur Discord lors de l'envoi "
            "dans le salon %s.",
            message.channel.id,
        )

    except Exception:

        logger.exception(
            "ERREUR INATTENDUE dans on_message "
            "| salon=%s | auteur=%s",
            message.channel.id,
            message.author.id,
        )

    finally:

        # Nécessaire pour que les commandes ! fonctionnent
        # malgré la surcharge de on_message.
        await bot.process_commands(
            message
        )


# ============================================================
# LANCEMENT
# ============================================================

bot.run(TOKEN)