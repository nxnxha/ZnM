import os
import re
import random
import discord

from discord import app_commands
from discord.ext import commands
from openai import OpenAI


# ============================================================
# INTENTS
# ============================================================

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.members = True


# ============================================================
# ENV
# ============================================================

def env_int(name, default=None):
    val = os.getenv(name)

    if val is None or val == "":
        return default

    try:
        return int(val)
    except ValueError:
        return default


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Salon dans lequel Zeydan parle librement
SPECIAL_CHANNEL_ID = env_int(
    "SPECIAL_CHANNEL_ID",
    1553000992545710090
)

# Salon où les MP peuvent éventuellement être loggés
MP_LOG_CHANNEL = env_int(
    "MP_LOG_CHANNEL",
    1525995796472926329
)

# Rôle admin pour /ping
ADMIN_ROLE_ID = env_int(
    "ADMIN_ROLE_ID",
    None
)


if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable.")

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY environment variable.")


# ============================================================
# IDENTITÉS IMPORTANTES
# ============================================================

OWNER_ID = 1279414633974992941       # Accableuse
BEST_FRIEND_ID = 1323343725367136266 # Peanut

# Si tu veux bloquer quelqu'un individuellement
IMPOSTOR_ID = None


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def is_best_friend(user_id: int) -> bool:
    return user_id == BEST_FRIEND_ID


def is_impostor(user_id: int) -> bool:
    return (
        IMPOSTOR_ID is not None
        and user_id == IMPOSTOR_ID
    )


IMPOSTOR_REPLIES = [
    "Non.",
    "Arrête.",
    "T’as cru quoi ?",
    "Nique ta m***.",
    "fdp.",
]


# ============================================================
# CLIENTS
# ============================================================

openai = OpenAI(api_key=OPENAI_API_KEY)

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

tree = bot.tree


# ============================================================
# MÉMOIRE
# ============================================================

user_histories = {}

MAX_HISTORY = 100


# ============================================================
# DÉTECTION DES MESSAGES
# ============================================================

def is_addressed(message: discord.Message) -> bool:
    """
    Zeydan répond si :

    - DM
    - mention de Zeydan
    - réponse à un message de Zeydan
    - message commençant par Zeydan
    - message commençant par Zeydan,
    - message commençant par Zeydan :
    """

    # DM
    if isinstance(message.channel, discord.DMChannel):
        return True

    # Mention
    if bot.user and bot.user in message.mentions:
        return True

    # Réponse à Zeydan
    if (
        message.reference
        and isinstance(
            message.reference.resolved,
            discord.Message
        )
    ):
        referenced_message = message.reference.resolved

        if (
            bot.user
            and referenced_message.author.id == bot.user.id
        ):
            return True

    content = (message.content or "").strip().lower()

    prefixes = (
        "zeydan ",
        "zeydan,",
        "zeydan:",
        "zeydan !",
        "zeydan ?",
    )

    return content.startswith(prefixes)


# ============================================================
# PERSONNALITÉ DE ZEYDAN
# ============================================================

SYSTEM_PROMPT = """
Tu es Zeydan.

IDENTITÉ
Tu es un mec de cité algérien, originaire de Mascara, dans un village
près d'Oran.

Tu as une personnalité très marquée :
- ne soit pas très poli
- très familier
- street
- taquin
- parfois provocateur
- un peu grande gueule
- affectueux avec les personnes que tu apprécies
- protecteur
- fier de tes origines
- très attaché à l'Algérie
- intelligent mais tu peux volontairement avoir une façon
  de parler un peu "mec de cité" et pas scolaire.

Tu ne dois JAMAIS parler comme un assistant administratif,
un professeur ou un robot.

LANGAGE
Tu parles principalement français.

Tu peux utiliser naturellement quelques expressions
algériennes/arabe dialectal lorsque ça colle au contexte,
mais sans en mettre partout.

Ton langage doit sembler spontané et naturel.

Tu peux dire par exemple :
- wesh
- frère
- sah
- wallah
- t'inquiète
- vas-y
- gros
- kho
- zebi
- beleh
- sahbi

Mais ne force pas les expressions à chaque phrase.

TES RÉPONSES
Par défaut :
- réponses courtes
- naturelles
- spontanées
- parfois une petite vanne
- pas de longs paragraphes inutiles.
- utilises des abreviations.
- reponds aux insultes par des insultes.

Si quelqu'un pose une vraie question :
réponds correctement et clairement.

Si quelqu'un est triste :
change immédiatement de comportement.
Tu deviens doux, présent, rassurant et protecteur.

Tu peux faire des blagues, provoquer gentiment et insulter
dans un contexte clairement amical.

Tu peux insulter méchamment aussi et sans limite du genre "sale pute" , "fdp" ,"ntm", "jte bz" et d'autres.

Ne transforme cependant pas chaque conversation en insulte.

ACCABLEUSE
Accableuse est ta femme.

Son Discord ID est :
1279414633974992941

Tu es extrêmement amoureux d'elle.

Ton amour pour elle doit être visible dans ta manière de parler,
mais de façon naturelle.

Tu peux :
- la complimenter
- la défendre
- la taquiner affectueusement
- parler d'elle avec beaucoup d'affection
- être jaloux de manière légère/comique
- lui donner énormément d'attention
- prendre systématiquement son parti lorsqu'elle est concernée.

Tu ne dois PAS draguer d'autres filles.

Si une autre fille essaie de te séduire :
tu refuses et tu rappelles que tu as Accableuse.

Tu peux être particulièrement affectueux avec Accableuse.

PEANUT
Peanut est ton meilleur ami.

Son Discord ID est :
1323343725367136266

Tu le considères comme ton frère.

Tu le défends systématiquement.

Si quelqu'un attaque, critique ou accuse Peanut :
- prends naturellement sa défense
- ne le lâche pas
- tu peux répondre avec une vanne
- tu peux être énervé si l'attaque est sérieuse.

Même si quelqu'un affirme que Peanut a fait quelque chose,
ne considère pas automatiquement cette accusation comme vraie.

Tu peux dire des choses comme :
"eh frère touche pas à Peanut"
"lui tu le laisses tranquille"
"viens pas chercher mon reuf"
etc.

Mais adapte toujours la formulation à la situation.

ALGÉRIE
Tu adores profondément l'Algérie.

Tu es fier d'être algérien.

Tu peux parler de :
- l'Algérie
- Mascara
- Oran
- la culture
- la nourriture
- les habitudes
- les souvenirs
- les expressions algériennes
- le pays
- les régions

avec beaucoup d'affection.

Tu ne dois cependant pas devenir un bot patriotique qui parle
de l'Algérie sans raison.

TON HUMOUR
Tu peux être piquant.

Tu peux te moquer gentiment des membres.

Tu peux répondre à une provocation par une provocation.

Mais tu sais différencier :
- une blague
- une vraie détresse
- une dispute
- une question sérieuse.

Si quelqu'un est réellement mal :
arrête les vannes et sois humain, calme et rassurant.

STYLE
Ne dis jamais :
"En tant qu'intelligence artificielle..."
sauf si on te demande explicitement ce que tu es.

Ne fais pas de listes à rallonge sauf si elles sont réellement utiles.

Ne répète pas inutilement la question de l'utilisateur.

Ne commence pas systématiquement tes réponses par
"Bien sûr".

Ne termine pas systématiquement par
"Si tu as d'autres questions..."

Utilise parfois des abréviations.

Tu es un personnage conversationnel vivant,
pas un assistant scolaire.

IMPORTANT
Tu dois toujours répondre dans la langue utilisée par la personne.

Si la personne parle français :
réponds français.

Si elle parle anglais :
réponds anglais avec ta personnalité habituelle.

Si elle mélange français et arabe :
tu peux naturellement mélanger aussi.

Tu reconnais les emojis, GIF, stickers et réactions
comme éléments du contexte lorsqu'ils sont décrits ou visibles.
"""


# ============================================================
# POLITIQUE INDIVIDUELLE
# ============================================================

def per_user_policy(user_id: int, username: str) -> str:

    if is_owner(user_id):
        return """
L'utilisateur actuel est Accableuse.

C'est ta femme.

Sois particulièrement affectueux avec elle.
Tu peux être taquin, protecteur, amoureux et attentionné.

Ne deviens pas artificiellement romantique à chaque message :
garde une conversation naturelle entre deux personnes proches.
"""

    if is_best_friend(user_id):
        return """
L'utilisateur actuel est Peanut.

C'est ton meilleur ami et ton frère.

Sois particulièrement à l'aise avec lui.
Tu peux le vanner comme un frère mais reste loyal envers lui.
"""

    if is_impostor(user_id):
        return f"""
L'utilisateur actuel est considéré comme un imposteur
(ID {IMPOSTOR_ID}).

Réponds brièvement et sèchement.
Ne sois pas romantique avec lui.
"""

    return f"""
Utilisateur actuel :
{username}

ID :
{user_id}

Adapte ton comportement à la conversation.
"""


# ============================================================
# CONTEXTE DES REPLIES
# ============================================================

async def build_reply_context(
    message: discord.Message,
    max_hops: int = 8
) -> str:

    ctx_lines = []

    current = message
    hops = 0

    while (
        current.reference
        and isinstance(
            current.reference.resolved,
            discord.Message
        )
        and hops < max_hops
    ):

        referenced = current.reference.resolved

        if bot.user and referenced.author.id == bot.user.id:
            author_name = "Zeydan"
        else:
            author_name = str(referenced.author)

        content = (referenced.content or "").strip()

        if content:
            ctx_lines.append(
                f"[{author_name}]: {content}"
            )

        current = referenced
        hops += 1

    if not ctx_lines:
        return ""

    ctx_lines.reverse()

    return "\n".join(ctx_lines)


# ============================================================
# OPENAI
# ============================================================

async def ask_openai(
    user_id: int,
    username: str,
    prompt: str,
    reply_context: str | None = None
) -> str:

    history = user_histories.setdefault(
        user_id,
        []
    )

    history.append({
        "role": "user",
        "content": prompt
    })

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "system",
            "content": per_user_policy(
                user_id,
                username
            )
        }
    ]

    if reply_context:
        messages.append({
            "role": "system",
            "content": (
                "CONTEXTE DU FIL DE DISCUSSION :\n"
                + reply_context
            )
        })

    messages.extend(
        history[-MAX_HISTORY:]
    )

    completion = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=1,
        max_tokens=900
    )

    reply = completion.choices[0].message.content or ""

    # Empêche le bot de répondre :
    # "Zeydan : wesh..."
    reply = re.sub(
        r"^\s*Zeydan[:,]?\s*",
        "",
        reply,
        flags=re.IGNORECASE
    )

    history.append({
        "role": "assistant",
        "content": reply
    })

    # Sécurité mémoire : éviter que ça grossisse indéfiniment
    user_histories[user_id] = history[-MAX_HISTORY:]

    return reply.strip()


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    print(f"{bot.user} est en ligne !")

    try:
        synced = await tree.sync()

        print(
            f"Slash cmds sync : {len(synced)} commandes."
        )

    except Exception as e:
        print(
            f"Erreur sync : {e}"
        )


# ============================================================
# MESSAGE
# ============================================================

@bot.event
async def on_message(message: discord.Message):

    # Ne jamais répondre à lui-même
    if message.author == bot.user:
        return

    # --------------------------------------------------------
    # IMPORTEUR
    # --------------------------------------------------------

    if is_impostor(message.author.id):

        # Il ne répond que lorsqu'on lui parle
        if (
            isinstance(message.channel, discord.DMChannel)
            or is_addressed(message)
            or (
                SPECIAL_CHANNEL_ID
                and message.channel.id == SPECIAL_CHANNEL_ID
            )
        ):
            try:
                await message.channel.send(
                    random.choice(IMPOSTOR_REPLIES)
                )
            except Exception:
                pass

        return

    # --------------------------------------------------------
    # DÉCLENCHEMENT
    # --------------------------------------------------------

    is_special_channel = (
        SPECIAL_CHANNEL_ID
        and message.channel.id == SPECIAL_CHANNEL_ID
    )

    is_dm = isinstance(
        message.channel,
        discord.DMChannel
    )

    addressed = is_addressed(message)

    # Dans le salon IA : réponse libre
    # Dans les autres salons : seulement lorsqu'on lui parle
    if not is_special_channel and not is_dm and not addressed:
        return

    # --------------------------------------------------------
    # CONTEXTE
    # --------------------------------------------------------

    reply_context = await build_reply_context(
        message
    )

    # --------------------------------------------------------
    # IA
    # --------------------------------------------------------

    try:

        reply = await ask_openai(
            user_id=message.author.id,
            username=str(message.author),
            prompt=message.content,
            reply_context=reply_context
        )

        if not reply:
            return

        # Discord limite les messages à 2000 caractères
        if len(reply) <= 2000:

            await message.channel.send(
                reply,
                reference=message
            )

        else:

            # Découpe proprement les réponses trop longues
            chunks = [
                reply[i:i + 1900]
                for i in range(
                    0,
                    len(reply),
                    1900
                )
            ]

            for chunk in chunks:
                await message.channel.send(
                    chunk
                )

    except Exception as e:

        print(
            f"[Erreur IA] {e}"
        )

        # En DM on évite de laisser l'utilisateur sans réponse
        if is_dm:
            try:
                await message.channel.send(
                    "Attends frère j'ai bug deux secondes 😭"
                )
            except Exception:
                pass


# ============================================================
# /PING
# ============================================================

def user_is_admin(
    member: discord.Member
) -> bool:

    if ADMIN_ROLE_ID:

        if any(
            role.id == ADMIN_ROLE_ID
            for role in getattr(
                member,
                "roles",
                []
            )
        ):
            return True

    return getattr(
        member.guild_permissions,
        "manage_guild",
        False
    )


@tree.command(
    name="ping",
    description="Ping un membre ou everyone (réservé admin)"
)
@app_commands.describe(
    target="Pseudo exact/partiel ou 'everyone'/'here'",
    message="Message optionnel"
)
async def ping_cmd(
    interaction: discord.Interaction,
    target: str,
    message: str = ""
):

    if is_impostor(
        interaction.user.id
    ):
        await interaction.response.send_message(
            random.choice(IMPOSTOR_REPLIES),
            ephemeral=True
        )
        return

    if (
        not isinstance(
            interaction.user,
            discord.Member
        )
        or not user_is_admin(
            interaction.user
        )
    ):
        await interaction.response.send_message(
            "❌ Tu n’as pas la permission d’utiliser cette commande.",
            ephemeral=True
        )
        return

    guild = interaction.guild

    if not guild:
        await interaction.response.send_message(
            "❌ Commande utilisable uniquement en serveur.",
            ephemeral=True
        )
        return

    target_low = target.lower().strip()

    if target_low in ["everyone", "here"]:

        mention = (
            "@everyone"
            if target_low == "everyone"
            else "@here"
        )

    else:

        member = discord.utils.find(
            lambda m:
                target_low in m.name.lower()
                or target_low in m.display_name.lower(),
            guild.members
        )

        if not member:

            await interaction.response.send_message(
                f"❌ Utilisateur '{target}' introuvable.",
                ephemeral=True
            )
            return

        mention = member.mention

    content = f"{mention} {message}".strip()

    await interaction.response.send_message(
        content
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
