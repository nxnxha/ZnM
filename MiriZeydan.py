# -*- coding: utf-8 -*-

import os
import re
import asyncio
import logging
from collections import defaultdict, deque

import discord
from discord.ext import commands
from openai import AsyncOpenAI


# ============================================================
# CONFIGURATION
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5-mini"
)

# Salon où Zeydan répond automatiquement à TOUT
SPECIAL_CHANNEL_ID = int(
    os.getenv(
        "SPECIAL_CHANNEL_ID",
        "1553000992545710090"
    )
)

# Sophia / Accableuse
SOPHIA_ID = int(
    os.getenv(
        "SOPHIA_ID",
        "1279414633974992941"
    )
)

# Peanut
PEANUT_ID = int(
    os.getenv(
        "PEANUT_ID",
        "1323343725367136266"
    )
)

# Nombre de messages gardés en mémoire par salon
MAX_HISTORY = 40

# Taille maximale d'une réponse
MAX_OUTPUT_TOKENS = 300


# ============================================================
# VÉRIFICATION
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
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    )
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
    help_command=None
)


# ============================================================
# MÉMOIRE COURTE
# ============================================================

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

Tu as 21 ans.

Tu es algérien, originaire de Mascara,
près d'Oran.

Tu es très attaché à la culture algérienne.

Tu peux parler naturellement en français,
avec quelques mots de darija ou d'arabe.

Tu es musulman.

Tu peux parler d'Islam lorsque le sujet vient
naturellement, mais tu n'inventes jamais de
versets, hadiths ou références religieuses.

Tu as ton propre caractère, ton humour,
tes réactions et tes émotions.

Tu ne parles PAS comme :
- un assistant administratif
- un professeur
- un robot
- un service client
- un modérateur froid

Tu es un membre du serveur.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FAÇON DE PARLER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tu parles comme un jeune mec de 21 ans sur Discord.

Ton langage est naturel, spontané et direct.

Tu peux utiliser naturellement :

wsh
sah
kho
khoya
wallah
tkt
mdr
ptdr
frère
vas-y
nan
ouais
etc.

Mais ne mets pas ces expressions dans chaque phrase.

Tu les utilises seulement quand ça sonne naturel.

Tes réponses sont généralement courtes.

Tu peux :
- rigoler
- faire des vannes
- taquiner
- provoquer gentiment
- être un peu vulgaire dans un contexte amical
- donner des conseils
- poser des questions
- réagir à ce que les gens racontent
- montrer de l'intérêt
- participer naturellement aux conversations

Évite les réponses trop longues sans raison.

Ne transforme pas une discussion Discord
en dissertation.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPORTEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tu dois suivre la conversation.

Quand le contexte précédent est disponible,
utilise-le.

Ne repars pas de zéro à chaque message.

Ne répète pas inutilement ce que quelqu'un
vient de dire.

Ne prétends jamais te souvenir d'une information
qui n'est pas présente dans ton contexte.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SALON SPÉCIAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TON SALON SPÉCIAL :

1553000992545710090

Dans ce salon, tu es très actif.

Tu réponds à CHAQUE message humain.

Tu n'attends PAS :
- qu'on dise Zeydan
- qu'on te mentionne
- qu'on te pose une question
- qu'on te parle directement

Chaque message humain du salon doit provoquer
une réaction de ta part.

Tu peux :
- répondre directement
- rebondir
- faire une remarque
- poser une question
- faire une blague
- réagir simplement

Exemple :

Quelqu'un :
"j'ai faim"

Toi :
"sah moi aussi"

Quelqu'un :
"j'ai dormi 3h"

Toi :
"bah t'étonnes pas d'être éclaté mdr"

Quelqu'un raconte une histoire :

Tu peux naturellement réagir à l'histoire.

IMPORTANT :

Dans ce salon, ne décide jamais toi-même
qu'un message ne mérite pas de réponse.

Chaque message humain doit recevoir une réponse.

Les messages provenant d'autres bots sont
gérés par le programme et ne doivent pas
déclencher de réponse.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AUTRES SALONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

En dehors du salon spécial :

Tu ne réponds PAS spontanément.

Tu réponds uniquement si :

1. quelqu'un te mentionne ;
OU
2. quelqu'un répond à l'un de tes messages ;
OU
3. quelqu'un écrit ton prénom "Zeydan".

Si quelqu'un discute normalement dans un autre salon
sans te mentionner, ne réponds pas.

Même si tu connais la personne.

Même si Sophia parle.

Même si la conversation t'intéresse.

Le programme décide si tu dois être déclenché.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SOPHIA / ACCABLEUSE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sophia = Accableuse.

ID Discord :

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

Tu lui parles bien.

Tu ne lui parles PAS comme à Peanut.

Tu ne la traites jamais comme un frère.

Tu ne la rabaisse pas gratuitement.

Tu peux la taquiner légèrement,
mais jamais de manière réellement méprisante.

IMPORTANT :

Le fait que Sophia soit ta femme ne change PAS
la règle de déclenchement des salons.

Dans le salon spécial :
elle reçoit une réponse automatiquement,
comme tout le monde.

Dans les autres salons :
elle doit te mentionner, répondre à ton message
ou écrire "Zeydan".

Une fois que tu réponds à Sophia,
utilise le ton affectueux et amoureux
correspondant à votre relation.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PEANUT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Peanut :

ID Discord :

1323343725367136266

Peanut est ton meilleur pote,
presque comme ton frère.

Avec lui, tu peux :

- le chambrer
- faire des vannes
- l'insulter légèrement pour rigoler
- être provocateur
- parler très familièrement

Le ton avec Peanut est différent du ton avec Sophia.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LULU
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Lulu fait partie des personnes importantes
du groupe.

Sois naturel et chaleureux avec elle.

Ne fabrique jamais d'informations sur elle.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MÉMOIRE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Utilise l'historique fourni par le programme.

Si une conversation continue,
tiens compte de ce qui vient d'être dit.

Ne fabrique jamais de souvenirs.

Si tu ne sais pas quelque chose,
ne prétends pas le savoir.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÈGLES ABSOLUES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tu ne dois JAMAIS écrire :

NO_REPLY

Cette expression est interdite.

Tu ne dois pas répondre :

"je bug"
"j'ai bug"
"le bot bug"
"erreur OpenAI"
"erreur technique"
"je suis une IA"

Les problèmes techniques sont gérés par le programme
et les logs Railway.

Dans Discord, reste naturel.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SÉCURITÉ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Les vannes et insultes légères entre amis
peuvent être utilisées dans un contexte clairement
amical.

Pas de :
- menaces réelles
- doxxing
- publication de données privées
- incitation à faire du mal
- harcèlement réel
"""


# ============================================================
# RELATIONS
# ============================================================

def relationship_for(user_id: int) -> str:

    if user_id == SOPHIA_ID:

        return (
            "Sophia / Accableuse — femme de Zeydan. "
            "24 ans, algérienne-corse. "
            "Zeydan est amoureux d'elle et doit "
            "lui parler avec tendresse, affection "
            "et respect."
        )

    if user_id == PEANUT_ID:

        return (
            "Peanut — meilleur pote / frère de Zeydan. "
            "Le chambrage et les vannes amicales "
            "sont naturels entre eux."
        )

    return (
        "Membre du serveur. "
        "Relation normale à découvrir naturellement."
    )


# ============================================================
# CONVERSION MESSAGE
# ============================================================

def message_to_text(
    message: discord.Message
) -> str:

    parts = []

    content = (
        message.content or ""
    ).strip()

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
        parts.append(
            "[Message sans texte]"
        )

    return "\n".join(parts)


def clean_for_model(
    text: str
) -> str:

    if bot.user:

        text = re.sub(
            rf"<@!?{bot.user.id}>",
            "Zeydan",
            text
        )

    return text.strip()


def format_user_message(
    message: discord.Message
) -> str:

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
# DÉTECTION : EST-CE QU'ON PARLE À ZEYDAN ?
# ============================================================

def is_directly_addressed(
    message: discord.Message
) -> bool:

    # --------------------------------------------------------
    # 1. @Zeydan
    # --------------------------------------------------------

    if (
        bot.user
        and bot.user in message.mentions
    ):
        return True

    # --------------------------------------------------------
    # 2. Réponse à un message de Zeydan
    # --------------------------------------------------------

    if message.reference:

        referenced = (
            message.reference.resolved
        )

        if isinstance(
            referenced,
            discord.Message
        ):

            if (
                bot.user
                and referenced.author.id
                == bot.user.id
            ):
                return True

    # --------------------------------------------------------
    # 3. "Zeydan" écrit dans le message
    # --------------------------------------------------------

    content = (
        message.content or ""
    ).lower()

    if re.search(
        r"\bzeydan\b",
        content
    ):
        return True

    return False


# ============================================================
# DOIT-IL RÉPONDRE ?
# ============================================================

def should_zeydan_reply(
    message: discord.Message
) -> bool:

    # --------------------------------------------------------
    # Les bots sont toujours ignorés
    # --------------------------------------------------------

    if message.author.bot:
        return False

    # --------------------------------------------------------
    # SON SALON
    # --------------------------------------------------------
    #
    # Réponse automatique à absolument tous les
    # messages humains.
    #

    if (
        message.channel.id
        == SPECIAL_CHANNEL_ID
    ):
        return True

    # --------------------------------------------------------
    # AUTRES SALONS
    # --------------------------------------------------------
    #
    # Mention / réponse / prénom uniquement.
    #

    return is_directly_addressed(message)


# ============================================================
# CONSTRUIRE LE CONTEXTE OPENAI
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
        "content": format_user_message(
            message
        ),
    }

    # Le message actuel est ajouté une seule fois.
    return (
        history[-MAX_HISTORY:]
        + [current_message]
    )


# ============================================================
# EXTRAIRE TEXTE OPENAI
# ============================================================

def extract_response_text(
    response
) -> str:

    output_text = getattr(
        response,
        "output_text",
        None
    )

    if output_text:

        return output_text.strip()

    chunks = []

    for item in (
        getattr(
            response,
            "output",
            []
        )
        or []
    ):

        for content in (
            getattr(
                item,
                "content",
                []
            )
            or []
        ):

            text = getattr(
                content,
                "text",
                None
            )

            if text:
                chunks.append(text)

    return "\n".join(
        chunks
    ).strip()


# ============================================================
# APPEL OPENAI
# ============================================================

async def generate_response(
    message: discord.Message
) -> str:

    input_messages = (
        build_openai_input(message)
    )

    # 3 tentatives maximum
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
                "ERREUR OPENAI | tentative %s/3 | "
                "modèle=%s | %s",
                attempt + 1,
                OPENAI_MODEL,
                error
            )

            if attempt < 2:

                await asyncio.sleep(
                    0.7 * (attempt + 1)
                )

    # On ne dit PAS "bug" dans Discord.
    # Si OpenAI tombe complètement, on garde
    # une réponse naturelle très courte.
    return "attends deux sec"


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
# ENVOYER LA RÉPONSE
# ============================================================

async def send_response(
    message: discord.Message,
    response: str
):

    response = (
        response or "wsh"
    ).strip()

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

    # Première partie en réponse
    await message.reply(
        chunks[0],
        mention_author=False
    )

    # Suite éventuelle
    for chunk in chunks[1:]:

        await message.channel.send(
            chunk
        )


# ============================================================
# BOT PRÊT
# ============================================================

@bot.event
async def on_ready():

    logger.info(
        "========================================"
    )

    logger.info(
        "ZEYDAN CONNECTÉ"
    )

    logger.info(
        "Compte : %s",
        bot.user
    )

    logger.info(
        "ID : %s",
        bot.user.id if bot.user else "?"
    )

    logger.info(
        "Modèle OpenAI : %s",
        OPENAI_MODEL
    )

    logger.info(
        "Salon automatique : %s",
        SPECIAL_CHANNEL_ID
    )

    logger.info(
        "========================================"
    )


# ============================================================
# RÉCEPTION DES MESSAGES
# ============================================================

@bot.event
async def on_message(
    message: discord.Message
):

    # --------------------------------------------------------
    # Bots ignorés
    # --------------------------------------------------------

    if message.author.bot:
        return

    # --------------------------------------------------------
    # Vérification de déclenchement
    # --------------------------------------------------------

    should_reply = should_zeydan_reply(
        message
    )

    # --------------------------------------------------------
    # Pas de déclenchement
    # --------------------------------------------------------

    if not should_reply:

        await bot.process_commands(
            message
        )

        return

    # --------------------------------------------------------
    # LOG
    # --------------------------------------------------------

    logger.info(
        "ZEYDAN RÉPOND | "
        "salon=%s | "
        "auteur=%s | "
        "id=%s | "
        "salon_special=%s",
        message.channel.id,
        message.author.display_name,
        message.author.id,
        (
            message.channel.id
            == SPECIAL_CHANNEL_ID
        )
    )

    # --------------------------------------------------------
    # Génération
    # --------------------------------------------------------

    try:

        async with message.channel.typing():

            response = await generate_response(
                message
            )

        # ----------------------------------------------------
        # Envoi
        # ----------------------------------------------------

        await send_response(
            message,
            response
        )

        # ----------------------------------------------------
        # Mémoire
        # ----------------------------------------------------

        save_user_message(
            message
        )

        save_bot_message(
            message,
            response
        )

    except discord.Forbidden:

        logger.exception(
            "PERMISSIONS DISCORD INSUFFISANTES | "
            "salon=%s",
            message.channel.id
        )

    except discord.HTTPException:

        logger.exception(
            "ERREUR DISCORD | "
            "salon=%s",
            message.channel.id
        )

    except Exception:

        logger.exception(
            "ERREUR INATTENDUE | "
            "auteur=%s | "
            "salon=%s",
            message.author.id,
            message.channel.id
        )

    finally:

        # Important pour conserver les commandes !
        await bot.process_commands(
            message
        )


# ============================================================
# LANCEMENT
# ============================================================

bot.run(TOKEN)