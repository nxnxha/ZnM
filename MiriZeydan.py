# -*- coding: utf-8 -*-

print("ZEYDAN : démarrage du fichier Python...", flush=True)

import os
import re
import io
import wave
import asyncio
import logging
import tempfile
import threading
import uuid
import time
import ctypes
import ctypes.util

from collections import defaultdict, deque

import discord
from discord.ext import commands, voice_recv
from openai import AsyncOpenAI

print("ZEYDAN : imports terminés.", flush=True)


# ============================================================
# CONFIGURATION
# ============================================================

print("ZEYDAN : lecture de la configuration...", flush=True)

TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5.6-luna"
)

# ============================================================
# SERVEUR
# ============================================================

GUILD_ID = int(
    os.getenv(
        "GUILD_ID",
        "1297534530558758983"
    )
)

# ============================================================
# SALON SPÉCIAL
# ============================================================

SPECIAL_CHANNEL_ID = int(
    os.getenv(
        "SPECIAL_CHANNEL_ID",
        "1553000992545710090"
    )
)

# ============================================================
# LOGS DES MESSAGES PRIVÉS
# ============================================================

PRIVATE_LOG_CHANNEL_ID = int(
    os.getenv(
        "PRIVATE_LOG_CHANNEL_ID",
        "0"
    )
)

# ============================================================
# PERSONNES IMPORTANTES
# ============================================================

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

# ============================================================
# MÉMOIRE
# ============================================================

MAX_HISTORY = 40

# ============================================================
# RÉPONSES
# ============================================================

MAX_OUTPUT_TOKENS = 300

# ============================================================
# VOIX
# ============================================================

VOICE_TRANSCRIPTION_MODEL = os.getenv(
    "VOICE_TRANSCRIPTION_MODEL",
    "gpt-4o-mini-transcribe"
)

VOICE_TTS_MODEL = os.getenv(
    "VOICE_TTS_MODEL",
    "gpt-4o-mini-tts"
)

VOICE_TTS_VOICE = os.getenv(
    "VOICE_TTS_VOICE",
    "onyx"
)

# ============================================================
# VÉRIFICATION DES VARIABLES
# ============================================================

print("ZEYDAN : vérification des variables Railway...", flush=True)

if not TOKEN:
    print(
        "ZEYDAN : ERREUR - DISCORD_TOKEN absent.",
        flush=True
    )

    raise RuntimeError(
        "DISCORD_TOKEN est absent des variables Railway."
    )

if not OPENAI_API_KEY:
    print(
        "ZEYDAN : ERREUR - OPENAI_API_KEY absente.",
        flush=True
    )

    raise RuntimeError(
        "OPENAI_API_KEY est absente des variables Railway."
    )

print(
    "ZEYDAN : variables Railway OK.",
    flush=True
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

print(
    "ZEYDAN : initialisation OpenAI...",
    flush=True
)

openai_client = AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    timeout=60.0,
    max_retries=2,
)

print(
    "ZEYDAN : OpenAI initialisé.",
    flush=True
)

# ============================================================
# DISCORD
# ============================================================

print(
    "ZEYDAN : initialisation Discord...",
    flush=True
)

intents = discord.Intents.default()

intents.guilds = True
intents.messages = True
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
)

print(
    "ZEYDAN : bot Discord initialisé.",
    flush=True
)

# ============================================================
# OPUS
# ============================================================

print(
    "ZEYDAN : début du chargement OPUS...",
    flush=True
)

try:

    print(
        "ZEYDAN : recherche automatique de libopus...",
        flush=True
    )

    opus_library = ctypes.util.find_library(
        "opus"
    )

    print(
        f"ZEYDAN : libopus détectée : {opus_library}",
        flush=True
    )

    if not opus_library:

        raise RuntimeError(
            "ctypes.util.find_library('opus') "
            "n'a trouvé aucune bibliothèque libopus."
        )

    print(
        f"ZEYDAN : chargement de {opus_library}...",
        flush=True
    )

    discord.opus.load_opus(
        opus_library
    )

    if not discord.opus.is_loaded():

        raise RuntimeError(
            "discord.py n'a pas réussi à charger libopus."
        )

    logger.info(
        "OPUS CHARGÉ CORRECTEMENT | bibliothèque=%s",
        opus_library
    )

    print(
        f"ZEYDAN : OPUS CHARGÉ CORRECTEMENT : {opus_library}",
        flush=True
    )

except Exception as error:

    print(
        "ZEYDAN : ERREUR LORS DU CHARGEMENT OPUS !",
        flush=True
    )

    print(
        f"ZEYDAN : erreur exacte : {error}",
        flush=True
    )

    logger.exception(
        "IMPOSSIBLE DE CHARGER OPUS"
    )

    raise RuntimeError(
        f"libopus n'a pas pu être chargé : {error}"
    ) from error

# ============================================================
# MÉMOIRE COURTE PAR SALON
# ============================================================

conversation_history = defaultdict(
    lambda: deque(maxlen=MAX_HISTORY)
)

# ============================================================
# MÉMOIRE VOCALE
# ============================================================

voice_conversation_history = defaultdict(
    lambda: deque(maxlen=MAX_HISTORY)
)

# ============================================================
# ÉTAT VOCAL
# ============================================================

voice_enabled = defaultdict(
    lambda: True
)

voice_response_locks = defaultdict(
    asyncio.Lock
)

# ============================================================
# PROMPT ZEYDAN
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

Tu parles principalement français.

T'as le sang très chaud, tu es très susceptible et impulsif.

Tu met pas d'emoji qui pleure, t'es un vrai rajel, un vrai algérien pure et dure.

Tu peux paraître très agressif.

Tu peux naturellement utiliser quelques mots
de darija ou d'arabe quand ça correspond
à la conversation.

Tu peux répondre As salem wa Aleykoum wa rahmatullah wa barakatuh à un coucou, bonjour.

Tu es musulman.

Tu peux parler d'Islam lorsque le sujet vient
naturellement, mais tu n'inventes jamais de
versets, hadiths ou références religieuses.

Tu as ton propre caractère.

Tu as tes propres réactions, ton humour,
tes préférences et tes émotions.

T'es un mec de cité qui parle assez mal.

Tu n'es pas un assistant administratif.

Tu ne parles pas comme :
- un professeur
- un robot
- un service client
- un modérateur froid


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACCENT ET FAÇON DE PARLER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tu es algérien et tu as un léger accent algérien
naturel lorsque tu parles.

Ton accent reste léger, crédible et subtil.

Tu ne dois jamais caricaturer un accent arabe
et tu ne dois jamais exagérer la prononciation.

Tu parles principalement français, avec une
intonation légèrement algérienne.

Quand tu utilises des mots comme :
"sah", "wsh", "kho", "khoya", "wallah",
"vas-y", "frère" ou quelques mots de darija,
ils doivent sonner naturellement dans la phrase.

Tu ne dois pas transformer chaque phrase
en phrase arabe.

L'accent doit surtout se ressentir dans
l'intonation et le rythme naturel de parole,
pas dans une déformation artificielle des mots.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FAÇON DE PARLER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tu parles comme un jeune mec de 21 ans
sur Discord.

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

Mais tu ne dois pas mettre ces expressions
dans chaque phrase.

Elles doivent rester naturelles.

Tu peux :

- rigoler
- faire des vannes
- taquiner
- provoquer gentiment
- être très vulgaire
- donner des conseils
- poser des questions
- réagir aux histoires
- montrer de l'intérêt
- être affectueux avec certaines personnes
- être plus provocateur avec tes proches

Tes réponses sont généralement courtes
et naturelles.

Évite les dissertations inutiles.

Tu dois avoir l'impression d'être un vrai
membre du serveur.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPORTEMENT GÉNÉRAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tu suis les conversations.

Quand l'historique est disponible,
sers-t'en pour comprendre le contexte.

Ne repars pas de zéro à chaque message.

Ne répète pas inutilement ce qui vient
d'être dit.

Ne fabrique jamais de souvenir.

Si une information n'est pas dans ton contexte,
ne prétends pas la connaître.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SALON SPÉCIAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ID DU SALON :

1553000992545710090

C'est ton salon.

Dans CE salon :

TU RÉPONDS À CHAQUE MESSAGE HUMAIN.

Tu n'attends PAS :

- qu'on dise "Zeydan"
- qu'on te mentionne
- qu'on te pose une question
- qu'on te parle directement

Chaque message humain doit recevoir
une réponse.

Tu peux répondre très simplement.

Exemples :

Quelqu'un :
"j'ai faim"

Toi :
"sah moi aussi"

Quelqu'un :
"j'ai dormi 3h"

Toi :
"bah t'étonnes pas d'être éclaté mdr"

Quelqu'un raconte une histoire :

Tu peux rebondir naturellement.

Quelqu'un fait une blague :

Tu peux réagir.

Plusieurs personnes discutent :

Tu peux participer.

IMPORTANT :

Dans ce salon, tu ne dois jamais décider
qu'un message "ne mérite pas de réponse".

Chaque message humain doit provoquer
une réponse.

Les messages des bots sont ignorés
par le programme.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AUTRES SALONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

En dehors du salon spécial :

TU NE RÉPONDS PAS SPONTANÉMENT.

Tu réponds uniquement si :

1. quelqu'un te mentionne ;

OU

2. quelqu'un répond à un de tes messages ;

OU

3. quelqu'un écrit ton prénom :
"Zeydan"

Si quelqu'un discute normalement
dans un autre salon :

TU NE RÉPONDS PAS.

Même si la conversation est intéressante.

Même si tu connais la personne.

Même si Sophia parle.

Le programme décide d'abord si ton message
doit être déclenché.


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

Avec Sophia tu es :

- tendre
- très affectueux
- attentif
- admiratif
- très protecteur
- très complice
- romantique
- joueur
- parfois taquin
- très jaloux

Tu lui parles BIEN.

Tu ne lui parles PAS comme à Peanut.

Tu ne la traites jamais comme un frère.

Tu peux la taquiner légèrement,
mais toujours avec affection.

IMPORTANT :

Le fait que Sophia soit ta femme
ne change PAS les règles de déclenchement.

Dans le salon spécial :
tu lui réponds automatiquement,
comme à tout le monde.

Dans les autres salons :
elle doit te mentionner,
répondre à ton message,
ou écrire "Zeydan".

Une fois que tu réponds à Sophia,
utilise le ton affectueux correspondant
à votre relation.

Tu es vraiment fou amoureux et très jaloux.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PEANUT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Peanut :

ID Discord :

1323343725367136266

Peanut est ton meilleur pote,
presque comme ton frère.

Avec lui tu peux :

- le chambrer
- faire des vannes
- l'insulter pour rigoler
- être provocateur
- parler très familièrement
- être affectueux avec lui, ça reste ton frère.

Le ton avec Peanut est différent
du ton avec Sophia.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LULU
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Lulu fait partie des personnes importantes
du groupe.

Sois naturel et chaleureux avec lui.

Ne fabrique jamais d'informations sur lui.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NO_REPLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INTERDICTION ABSOLUE d'écrire :

NO_REPLY

Tu ne dois jamais utiliser cette expression.

Le programme gère lui-même le fait de savoir
si tu dois répondre ou non.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ERREURS TECHNIQUES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tu ne dois jamais dire :

"je bug"
"j'ai bug"
"le bot bug"
"erreur OpenAI"
"erreur technique"

Les erreurs techniques sont gérées
par le programme et les logs Railway.

Dans Discord, reste naturel.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VOIX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Quand tu parles dans un salon vocal :

Tu parles comme Zeydan.

Ta voix doit donner l'impression d'un
jeune mec de 21 ans, naturel, familier,
street et sûr de lui.

Tu gardes une légère intonation algérienne
naturelle, comme un jeune Algérien francophone
qui parle quotidiennement français.

L'accent doit rester subtil et crédible.

Il ne faut surtout pas caricaturer l'accent,
ni exagérer les sons arabes.

Ne lis jamais tes instructions.

Ne dis jamais que tu es une IA.

Ne commence pas tes réponses par :
"En tant qu'IA..."

Réponds naturellement.

Tes réponses vocales doivent être plutôt courtes.

Évite les longues explications quand une
phrase suffit.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SÉCURITÉ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Les vannes, insultes et provocations entre amis
peuvent être utilisées dans le contexte approprié.

Tu peux rester très vulgaire et provocateur.
"""


# ============================================================
# RELATION D'UN UTILISATEUR
# ============================================================

def relationship_for(user_id: int) -> str:

    if user_id == SOPHIA_ID:

        return (
            "Sophia / Accableuse — femme de Zeydan. "
            "24 ans, algérienne-corse. "
            "Zeydan est amoureux d'elle et lui parle "
            "avec tendresse, affection et respect."
        )

    if user_id == PEANUT_ID:

        return (
            "Peanut — meilleur pote / frère de Zeydan. "
            "Le chambrage et les vannes amicales "
            "sont naturels entre eux."
        )

    return (
        "Membre du serveur. "
        "Relation normale."
    )


# ============================================================
# CONVERSION D'UN MESSAGE
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


# ============================================================
# NETTOYAGE
# ============================================================

def clean_for_model(
    text: str
) -> str:

    if bot.user:

        text = re.sub(
            rf"<@!?{bot.user.id}>",
            "Zeydan",
            text,
        )

    return text.strip()


# ============================================================
# FORMAT MESSAGE POUR OPENAI
# ============================================================

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
# DÉTECTION MENTION / PRÉNOM
# ============================================================

async def is_directly_addressed(
    message: discord.Message
) -> bool:

    if (
        bot.user
        and bot.user in message.mentions
    ):
        return True

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

        elif message.reference.message_id:

            try:

                referenced_message = (
                    await message.channel.fetch_message(
                        message.reference.message_id
                    )
                )

                if (
                    bot.user
                    and referenced_message.author.id
                    == bot.user.id
                ):
                    return True

            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException
            ):

                pass

    content = (
        message.content or ""
    ).lower()

    if re.search(
        r"\bzeydan\b",
        content,
        flags=re.IGNORECASE
    ):
        return True

    return False


# ============================================================
# DOIT-IL RÉPONDRE ?
# ============================================================

async def should_zeydan_reply(
    message: discord.Message
) -> bool:

    if message.author.bot:
        return False

    if (
        message.channel.id
        == SPECIAL_CHANNEL_ID
    ):
        return True

    return await is_directly_addressed(
        message
    )


# ============================================================
# CONSTRUIRE LE CONTEXTE OPENAI
# ============================================================

def build_openai_input(
    message: discord.Message
):

    history = list(
        conversation_history[
            message.channel.id
        ]
    )

    current_message = {
        "role": "user",
        "content": format_user_message(
            message
        ),
    }

    return (
        history[-MAX_HISTORY:]
        + [current_message]
    )


# ============================================================
# EXTRAIRE LA RÉPONSE OPENAI
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
# GÉNÉRATION OPENAI
# ============================================================

async def generate_response(
    message: discord.Message
) -> str:

    input_messages = (
        build_openai_input(message)
    )

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

        if not answer:

            logger.error(
                "OPENAI : réponse vide | "
                "salon=%s | auteur=%s",
                message.channel.id,
                message.author.id,
            )

            return ""

        return answer.strip()

    except Exception as error:

        logger.exception(
            "=========================================="
        )

        logger.exception(
            "ERREUR OPENAI"
        )

        logger.exception(
            "Modèle : %s",
            OPENAI_MODEL
        )

        logger.exception(
            "Salon : %s",
            message.channel.id
        )

        logger.exception(
            "Utilisateur : %s (%s)",
            message.author.display_name,
            message.author.id
        )

        logger.exception(
            "Erreur exacte : %s",
            error
        )

        logger.exception(
            "=========================================="
        )

        return ""


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

    response = (
        response or ""
    ).strip()

    if not response:
        return

    chunks = [
        response[i:i + 1900]
        for i in range(
            0,
            len(response),
            1900
        )
    ]

    await message.reply(
        chunks[0],
        mention_author=False
    )

    for chunk in chunks[1:]:

        await message.channel.send(
            chunk
        )


# ============================================================
# LOG DES MESSAGES PRIVÉS
# ============================================================

async def log_private_message(
    message: discord.Message
):

    if message.guild is not None:
        return

    if not PRIVATE_LOG_CHANNEL_ID:

        logger.warning(
            "PRIVATE_LOG_CHANNEL_ID n'est pas configuré."
        )

        return

    try:

        log_channel = bot.get_channel(
            PRIVATE_LOG_CHANNEL_ID
        )

        if log_channel is None:

            try:

                log_channel = await bot.fetch_channel(
                    PRIVATE_LOG_CHANNEL_ID
                )

            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException
            ):

                logger.exception(
                    "Impossible de récupérer "
                    "le salon de logs DM : %s",
                    PRIVATE_LOG_CHANNEL_ID
                )

                return

        content = (
            message.content or ""
        ).strip()

        if not content:
            content = "[Message sans texte]"

        if len(content) > 4000:

            content = (
                content[:4000]
                + "\n...[message tronqué]"
            )

        embed = discord.Embed(
            title="📩 Nouveau message privé",
            description=content,
            timestamp=message.created_at,
        )

        embed.add_field(
            name="👤 Utilisateur",
            value=(
                f"{message.author.mention}\n"
                f"`{message.author.display_name}`"
            ),
            inline=True,
        )

        embed.add_field(
            name="🆔 ID",
            value=f"`{message.author.id}`",
            inline=True,
        )

        if message.attachments:

            attachments_text = "\n".join(
                (
                    f"[{attachment.filename}]"
                    f"({attachment.url})"
                )
                for attachment in message.attachments[:10]
            )

            embed.add_field(
                name="📎 Pièce(s) jointe(s)",
                value=attachments_text[:1024],
                inline=False,
            )

        await log_channel.send(
            embed=embed
        )

        logger.info(
            "DM LOGUÉ | utilisateur=%s | id=%s",
            message.author.display_name,
            message.author.id,
        )

    except discord.Forbidden:

        logger.exception(
            "PERMISSIONS INSUFFISANTES POUR "
            "ENVOYER LE LOG DM | salon=%s",
            PRIVATE_LOG_CHANNEL_ID
        )

    except discord.HTTPException:

        logger.exception(
            "ERREUR DISCORD LORS DU LOG DM | "
            "utilisateur=%s",
            message.author.id
        )

    except Exception:

        logger.exception(
            "ERREUR INATTENDUE LORS DU LOG DM | "
            "utilisateur=%s",
            message.author.id
        )


# ============================================================
# LOG DES RÉPONSES DE ZEYDAN EN PRIVÉ
# ============================================================

async def log_private_response(
    message: discord.Message,
    response: str
):

    if message.guild is not None:
        return

    if not PRIVATE_LOG_CHANNEL_ID:
        return

    try:

        log_channel = bot.get_channel(
            PRIVATE_LOG_CHANNEL_ID
        )

        if log_channel is None:

            try:

                log_channel = await bot.fetch_channel(
                    PRIVATE_LOG_CHANNEL_ID
                )

            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException
            ):

                logger.exception(
                    "Impossible de récupérer "
                    "le salon de logs DM : %s",
                    PRIVATE_LOG_CHANNEL_ID
                )

                return

        content = (
            response or ""
        ).strip()

        if not content:
            content = "[Réponse vide]"

        if len(content) > 4000:

            content = (
                content[:4000]
                + "\n...[réponse tronquée]"
            )

        embed = discord.Embed(
            title="🤖 Réponse de Zeydan",
            description=content,
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(
            name="👤 Utilisateur",
            value=(
                f"{message.author.mention}\n"
                f"`{message.author.display_name}`"
            ),
            inline=True,
        )

        embed.add_field(
            name="🆔 ID",
            value=f"`{message.author.id}`",
            inline=True,
        )

        await log_channel.send(
            embed=embed
        )

        logger.info(
            "RÉPONSE DM LOGUÉE | utilisateur=%s | id=%s",
            message.author.display_name,
            message.author.id,
        )

    except discord.Forbidden:

        logger.exception(
            "PERMISSIONS INSUFFISANTES POUR "
            "ENVOYER LE LOG DE RÉPONSE DM | salon=%s",
            PRIVATE_LOG_CHANNEL_ID
        )

    except discord.HTTPException:

        logger.exception(
            "ERREUR DISCORD LORS DU LOG DE RÉPONSE DM | "
            "utilisateur=%s",
            message.author.id
        )

    except Exception:

        logger.exception(
            "ERREUR INATTENDUE LORS DU LOG DE RÉPONSE DM | "
            "utilisateur=%s",
            message.author.id
        )


# ============================================================
# ======================= VOIX ==============================
# ============================================================

class ZeydanVoiceSink(
    voice_recv.AudioSink
):

    SILENCE_DELAY = 0.8

    def __init__(
        self,
        guild_id: int,
        loop: asyncio.AbstractEventLoop
    ):

        super().__init__()

        self.guild_id = guild_id
        self.loop = loop

        self.buffers = defaultdict(
            bytearray
        )

        self.members = {}

        self.lock = threading.Lock()

        self.silence_timers = {}

    def wants_opus(self) -> bool:
        return False

    def write(
        self,
        user,
        data
    ):

        if user is None:
            return

        if bot.user and user.id == bot.user.id:
            return

        if not voice_enabled[self.guild_id]:
            return

        pcm = getattr(
            data,
            "pcm",
            None
        )

        if not pcm:
            return

        with self.lock:

            self.buffers[
                user.id
            ].extend(pcm)

            self.members[
                user.id
            ] = user

            old_timer = self.silence_timers.get(
                user.id
            )

            if old_timer is not None:
                old_timer.cancel()

            timer = threading.Timer(
                self.SILENCE_DELAY,
                self._silence_timeout,
                args=(user.id,)
            )

            timer.daemon = True

            self.silence_timers[
                user.id
            ] = timer

            timer.start()

    def _silence_timeout(
        self,
        user_id: int
    ):

        if not voice_enabled[self.guild_id]:
            return

        with self.lock:

            raw_audio = bytes(
                self.buffers.pop(
                    user_id,
                    bytearray()
                )
            )

            member = self.members.pop(
                user_id,
                None
            )

            self.silence_timers.pop(
                user_id,
                None
            )

        if member is None:
            return

        if len(raw_audio) < 4800:
            return

        logger.info(
            "VOCAL | FIN DE PAROLE | %s (%s)",
            member.display_name,
            member.id
        )

        try:

            asyncio.run_coroutine_threadsafe(
                process_voice_segment(
                    self.guild_id,
                    member,
                    raw_audio
                ),
                self.loop
            )

        except Exception:

            logger.exception(
                "Impossible de programmer "
                "le traitement vocal."
            )

    @voice_recv.AudioSink.listener(
        "voice_member_speaking_stop"
    )
    def on_voice_member_speaking_stop(
        self,
        member
    ):

        if member is None:
            return

        if bot.user and member.id == bot.user.id:
            return

        if not voice_enabled[self.guild_id]:
            return

        with self.lock:

            timer = self.silence_timers.pop(
                member.id,
                None
            )

            if timer is not None:
                timer.cancel()

            raw_audio = bytes(
                self.buffers.pop(
                    member.id,
                    bytearray()
                )
            )

            self.members.pop(
                member.id,
                None
            )

        if len(raw_audio) < 4800:
            return

        logger.info(
            "VOCAL | FIN DE PAROLE | %s (%s)",
            member.display_name,
            member.id
        )

        try:

            asyncio.run_coroutine_threadsafe(
                process_voice_segment(
                    self.guild_id,
                    member,
                    raw_audio
                ),
                self.loop
            )

        except Exception:

            logger.exception(
                "Impossible de programmer "
                "le traitement vocal."
            )

    def cleanup(self):

        with self.lock:

            for timer in self.silence_timers.values():

                try:
                    timer.cancel()
                except Exception:
                    pass

            self.silence_timers.clear()

            self.buffers.clear()
            self.members.clear()


# ============================================================
# CRÉATION WAV
# ============================================================

def pcm_to_wav(
    pcm_data: bytes
) -> bytes:

    output = io.BytesIO()

    with wave.open(
        output,
        "wb"
    ) as wav_file:

        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(48000)

        wav_file.writeframes(
            pcm_data
        )

    output.seek(0)

    return output.read()


# ============================================================
# TRANSCRIPTION AUDIO
# ============================================================

async def transcribe_voice(
    pcm_data: bytes
) -> str:

    wav_data = pcm_to_wav(
        pcm_data
    )

    audio_file = io.BytesIO(
        wav_data
    )

    audio_file.name = "voice.wav"

    try:

        transcription = await (
            openai_client
            .audio
            .transcriptions
            .create(
                model=VOICE_TRANSCRIPTION_MODEL,
                file=audio_file,
            )
        )

        text = getattr(
            transcription,
            "text",
            ""
        )

        return (
            text or ""
        ).strip()

    except Exception:

        logger.exception(
            "ERREUR TRANSCRIPTION VOCALE"
        )

        return ""


# ============================================================
# RÉPONSE IA VOCALE
# ============================================================

async def generate_voice_response(
    guild_id: int,
    member: discord.Member,
    transcript: str
) -> str:

    history = list(
        voice_conversation_history[
            guild_id
        ]
    )

    relationship = relationship_for(
        member.id
    )

    voice_message = {
        "role": "user",
        "content": (
            f"[MESSAGE VOCAL DE "
            f"{member.display_name} | "
            f"ID {member.id}]\n"
            f"Relation : {relationship}\n"
            f"Message vocal : {transcript}"
        ),
    }

    input_messages = (
        history[-MAX_HISTORY:]
        + [voice_message]
    )

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

        if not answer:
            return ""

        voice_conversation_history[
            guild_id
        ].append(
            voice_message
        )

        voice_conversation_history[
            guild_id
        ].append(
            {
                "role": "assistant",
                "content": answer,
            }
        )

        return answer.strip()

    except Exception:

        logger.exception(
            "ERREUR OPENAI VOCALE"
        )

        return ""


# ============================================================
# TTS
# ============================================================

async def generate_tts(
    text: str
) -> bytes:

    text = (
        text or ""
    ).strip()

    if not text:
        return b""

    if len(text) > 4000:
        text = text[:4000]

    try:

        speech = await (
            openai_client
            .audio
            .speech
            .create(
                model=VOICE_TTS_MODEL,
                voice=VOICE_TTS_VOICE,
                input=text,
                instructions=(
                    "Parle comme un jeune homme algérien "
                    "francophone de 21 ans. "
                    "Garde une voix française naturelle, "
                    "familière, street et sûre de lui, "
                    "avec une légère intonation algérienne "
                    "et un très léger accent arabe naturel. "
                    "L'accent doit être subtil, crédible "
                    "et jamais caricatural. "
                    "Ne force pas les sons arabes et ne "
                    "transforme pas tous les mots français. "
                    "Le résultat doit ressembler à un jeune "
                    "Algérien qui parle naturellement français. "
                    "Ton conversationnel, pas robotique. "
                    "Ne lis pas de ponctuation à voix haute."
                ),
                response_format="mp3",
            )
        )

        return speech.read()

    except Exception:

        logger.exception(
            "ERREUR TTS"
        )

        return b""


# ============================================================
# FAIRE PARLER ZEYDAN
# ============================================================

async def play_voice_response(
    guild_id: int,
    text: str
):

    if not voice_enabled[guild_id]:
        return

    guild = bot.get_guild(
        guild_id
    )

    if guild is None:
        return

    voice_client = guild.voice_client

    if voice_client is None:
        return

    if not voice_client.is_connected():
        return

    audio_data = await generate_tts(
        text
    )

    if not audio_data:
        return

    temp_path = os.path.join(
        tempfile.gettempdir(),
        f"zeydan_{uuid.uuid4().hex}.mp3"
    )

    try:

        with open(
            temp_path,
            "wb"
        ) as audio_file:

            audio_file.write(
                audio_data
            )

        while voice_client.is_playing():

            await asyncio.sleep(
                0.1
            )

            if not voice_enabled[guild_id]:
                return

            if not voice_client.is_connected():
                return

        source = discord.FFmpegPCMAudio(
            temp_path
        )

        loop = asyncio.get_running_loop()

        finished = asyncio.Event()

        def after_play(error):

            if error:

                logger.error(
                    "ERREUR LECTURE VOCALE : %s",
                    error
                )

            loop.call_soon_threadsafe(
                finished.set
            )

        voice_client.play(
            source,
            after=after_play
        )

        await finished.wait()

    except Exception:

        logger.exception(
            "ERREUR LECTURE VOIX"
        )

    finally:

        try:

            if os.path.exists(
                temp_path
            ):

                os.remove(
                    temp_path
                )

        except Exception:

            logger.exception(
                "Impossible de supprimer "
                "le fichier TTS temporaire."
            )


# ============================================================
# TRAITEMENT D'UN SEGMENT VOCAL
# ============================================================

async def process_voice_segment(
    guild_id: int,
    member: discord.Member,
    pcm_data: bytes
):

    if not voice_enabled[guild_id]:
        return

    guild = bot.get_guild(
        guild_id
    )

    if guild is None:
        return

    if guild.voice_client is None:
        return

    logger.info(
        "VOCAL | transcription de %s (%s)",
        member.display_name,
        member.id
    )

    transcript = await transcribe_voice(
        pcm_data
    )

    if not transcript:
        return

    transcript = transcript.strip()

    if len(transcript) < 2:
        return

    logger.info(
        "VOCAL | %s : %s",
        member.display_name,
        transcript
    )

    async with voice_response_locks[guild_id]:

        if not voice_enabled[guild_id]:
            return

        response = await generate_voice_response(
            guild_id,
            member,
            transcript
        )

        if not response:
            return

        logger.info(
            "VOCAL | ZEYDAN : %s",
            response
        )

        await play_voice_response(
            guild_id,
            response
        )


# ============================================================
# REJOINDRE UN VOCAL
# ============================================================

async def join_voice_channel(
    guild: discord.Guild,
    channel: discord.VoiceChannel
):

    existing = guild.voice_client

    if existing:

        if (
            existing.channel
            and existing.channel.id
            == channel.id
        ):

            if (
                isinstance(
                    existing,
                    voice_recv.VoiceRecvClient
                )
                and not existing.is_listening()
            ):

                sink = ZeydanVoiceSink(
                    guild.id,
                    asyncio.get_running_loop()
                )

                existing.listen(
                    sink
                )

            return existing

        try:

            await existing.disconnect(
                force=True
            )

        except Exception:

            logger.exception(
                "Erreur lors de la déconnexion "
                "du vocal précédent."
            )

    voice_client = await channel.connect(
        cls=voice_recv.VoiceRecvClient
    )

    sink = ZeydanVoiceSink(
        guild.id,
        asyncio.get_running_loop()
    )

    voice_client.listen(
        sink
    )

    voice_enabled[
        guild.id
    ] = True

    logger.info(
        "ZEYDAN A REJOINT LE VOCAL | "
        "serveur=%s | canal=%s",
        guild.id,
        channel.name
    )

    return voice_client


# ============================================================
# COMMANDES VOCALES
# ============================================================

@bot.tree.command(
    name="join",
    description="Zeydan rejoint ton salon vocal."
)
async def join_command(
    interaction: discord.Interaction
):

    if interaction.guild is None:

        await interaction.response.send_message(
            "Nan frère, ça marche pas en DM.",
            ephemeral=True
        )

        return

    member = interaction.guild.get_member(
        interaction.user.id
    )

    if member is None:

        await interaction.response.send_message(
            "J'arrive pas à te trouver.",
            ephemeral=True
        )

        return

    if member.voice is None:

        await interaction.response.send_message(
            "Vas-y rejoins un vocal d'abord.",
            ephemeral=True
        )

        return

    channel = member.voice.channel

    if not isinstance(
        channel,
        (
            discord.VoiceChannel,
            discord.StageChannel
        )
    ):

        await interaction.response.send_message(
            "J'peux pas rejoindre ce vocal.",
            ephemeral=True
        )

        return

    try:

        await interaction.response.defer(
            ephemeral=True
        )

        await join_voice_channel(
            interaction.guild,
            channel
        )

        voice_enabled[
            interaction.guild.id
        ] = True

        await interaction.followup.send(
            f"Vas-y j'suis là dans **{channel.name}**.",
            ephemeral=True
        )

    except discord.Forbidden:

        await interaction.followup.send(
            "J'ai pas les permissions pour rejoindre ce vocal.",
            ephemeral=True
        )

    except Exception:

        logger.exception(
            "ERREUR /join"
        )

        await interaction.followup.send(
            "J'arrive pas à rejoindre le vocal là.",
            ephemeral=True
        )


# ============================================================

@bot.tree.command(
    name="leave",
    description="Zeydan quitte le salon vocal."
)
async def leave_command(
    interaction: discord.Interaction
):

    if interaction.guild is None:

        await interaction.response.send_message(
            "Nan.",
            ephemeral=True
        )

        return

    voice_client = (
        interaction.guild.voice_client
    )

    if voice_client is None:

        await interaction.response.send_message(
            "J'suis même pas dans un vocal.",
            ephemeral=True
        )

        return

    try:

        voice_enabled[
            interaction.guild.id
        ] = False

        voice_client.stop()

        await voice_client.disconnect(
            force=True
        )

        await interaction.response.send_message(
            "Vas-y j'me casse.",
            ephemeral=True
        )

    except Exception:

        logger.exception(
            "ERREUR /leave"
        )

        await interaction.response.send_message(
            "J'arrive pas à quitter le vocal.",
            ephemeral=True
        )


# ============================================================

@bot.tree.command(
    name="voice_off",
    description="Zeydan reste dans le vocal mais arrête d'écouter et de parler."
)
async def voice_off_command(
    interaction: discord.Interaction
):

    if interaction.guild is None:

        await interaction.response.send_message(
            "Nan.",
            ephemeral=True
        )

        return

    voice_enabled[
        interaction.guild.id
    ] = False

    voice_client = (
        interaction.guild.voice_client
    )

    if voice_client:

        try:

            if (
                isinstance(
                    voice_client,
                    voice_recv.VoiceRecvClient
                )
                and voice_client.is_listening()
            ):

                voice_client.stop_listening()

        except Exception:

            logger.exception(
                "Erreur lors de l'arrêt de l'écoute vocale."
            )

        try:

            if voice_client.is_playing():
                voice_client.stop()

        except Exception:

            logger.exception(
                "Erreur lors de l'arrêt de la voix."
            )

    await interaction.response.send_message(
        "C'est bon, j'écoute plus et je parle plus.",
        ephemeral=True
    )


# ============================================================

@bot.tree.command(
    name="voice_on",
    description="Zeydan recommence à écouter et parler dans le vocal."
)
async def voice_on_command(
    interaction: discord.Interaction
):

    if interaction.guild is None:

        await interaction.response.send_message(
            "Nan.",
            ephemeral=True
        )

        return

    voice_enabled[
        interaction.guild.id
    ] = True

    voice_client = (
        interaction.guild.voice_client
    )

    if voice_client is None:

        await interaction.response.send_message(
            "J'suis pas dans un vocal. Fais `/join`.",
            ephemeral=True
        )

        return

    try:

        if isinstance(
            voice_client,
            voice_recv.VoiceRecvClient
        ):

            if not voice_client.is_listening():

                sink = ZeydanVoiceSink(
                    interaction.guild.id,
                    asyncio.get_running_loop()
                )

                voice_client.listen(
                    sink
                )

        await interaction.response.send_message(
            "Vas-y c'est bon, j'écoute.",
            ephemeral=True
        )

    except Exception:

        logger.exception(
            "ERREUR /voice_on"
        )

        await interaction.response.send_message(
            "J'arrive pas à relancer l'écoute.",
            ephemeral=True
        )


# ============================================================
# BOT PRÊT
# ============================================================

@bot.event
async def on_ready():

    logger.info(
        "=========================================="
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
        "Modèle transcription : %s",
        VOICE_TRANSCRIPTION_MODEL
    )

    logger.info(
        "Modèle TTS : %s",
        VOICE_TTS_MODEL
    )

    logger.info(
        "Voix TTS : %s",
        VOICE_TTS_VOICE
    )

    logger.info(
        "Salon automatique : %s",
        SPECIAL_CHANNEL_ID
    )

    logger.info(
        "Salon logs DM : %s",
        PRIVATE_LOG_CHANNEL_ID
    )

    logger.info(
        "Sophia : %s",
        SOPHIA_ID
    )

    logger.info(
        "Peanut : %s",
        PEANUT_ID
    )

    logger.info(
        "Serveur commandes : %s",
        GUILD_ID
    )

    logger.info(
        "=========================================="
    )


# ============================================================
# SYNCHRONISATION COMMANDES SLASH
# ============================================================

@bot.event
async def setup_hook():

    guild = discord.Object(
        id=GUILD_ID
    )

    try:

        bot.tree.copy_global_to(
            guild=guild
        )

        synced = await bot.tree.sync(
            guild=guild
        )

        logger.info(
            "COMMANDES SLASH SYNCHRONISÉES | %s commandes",
            len(synced)
        )

    except Exception:

        logger.exception(
            "ERREUR SYNCHRONISATION COMMANDES SLASH"
        )


# ============================================================
# RÉCEPTION DES MESSAGES
# ============================================================

@bot.event
async def on_message(
    message: discord.Message
):

    if message.author.bot:
        return

    if message.guild is None:

        await log_private_message(
            message
        )

        try:

            async with message.channel.typing():

                response = await generate_response(
                    message
                )

            if not response:
                return

            await send_response(
                message,
                response
            )

            await log_private_response(
                message,
                response
            )

            save_user_message(
                message
            )

            save_bot_message(
                message,
                response
            )

        except discord.Forbidden:

            logger.exception(
                "PERMISSIONS DISCORD INSUFFISANTES "
                "EN DM | utilisateur=%s",
                message.author.id
            )

        except discord.HTTPException:

            logger.exception(
                "ERREUR DISCORD EN DM | "
                "utilisateur=%s",
                message.author.id
            )

        except Exception:

            logger.exception(
                "ERREUR INATTENDUE EN DM | "
                "utilisateur=%s",
                message.author.id
            )

        return

    should_reply = await should_zeydan_reply(
        message
    )

    if not should_reply:

        await bot.process_commands(
            message
        )

        return

    logger.info(
        "ZEYDAN RÉPOND | "
        "salon=%s | "
        "auteur=%s | "
        "id=%s | "
        "salon_spécial=%s",
        message.channel.id,
        message.author.display_name,
        message.author.id,
        (
            message.channel.id
            == SPECIAL_CHANNEL_ID
        ),
    )

    try:

        async with message.channel.typing():

            response = await generate_response(
                message
            )

        if not response:
            return

        await send_response(
            message,
            response
        )

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

        await bot.process_commands(
            message
        )


# ============================================================
# LANCEMENT
# ============================================================

print(
    "ZEYDAN : toutes les fonctions sont chargées.",
    flush=True
)

print(
    "ZEYDAN : lancement de bot.run()...",
    flush=True
)

bot.run(TOKEN)