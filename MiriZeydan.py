import os
import re
import json
import random
import discord
from discord import app_commands
from discord.ext import commands
from openai import OpenAI
from datetime import timedelta

# ---------------- Intents ----------------
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.members = True

# ---------------- Env ----------------
def env_int(name, default=None):
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Channel/role IDs (overrideable via env)
SPECIAL_CHANNEL_ID   = env_int("SPECIAL_CHANNEL_ID", 1453132607788285982)   # Salon IA
SANCTION_LOG_CHANNEL = env_int("SANCTION_LOG_CHANNEL", ) # Logs sanctions
AUTHORIZED_MENTION_ROLE = env_int("AUTHORIZED_MENTION_ROLE", )  # (non utilisé ici)
MP_LOG_CHANNEL       = env_int("MP_LOG_CHANNEL",1461349026334245031)       # Logs MP
ADMIN_ROLE_ID        = env_int("ADMIN_ROLE_ID", )        # Rôle admin pour /ping

# ✨ Options “Mimi” (facultatives)
MIMI_WEBHOOK_NAME = os.getenv("MIMI_WEBHOOK_NAME", "Mimi")
MIMI_AVATAR_URL   = os.getenv("MIMI_AVATAR_URL", "")  # URL http(s) vers avatar si tu veux

if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable.")
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY environment variable.")

# ---------------- PROTECT (identité) ----------------
OWNER_ID    = 1359569212531675167 # sofiya
IMPOSTOR_ID = None                         # mets un int si tu veux bloquer quelqu’un

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def is_impostor(user_id: int) -> bool:
    return (IMPOSTOR_ID is not None) and (user_id == IMPOSTOR_ID)

# Répliques sèches pour l'imposteur
IMPOSTOR_REPLIES = [
    "Non.",
    "Arrête.",
    "T’as cru quoi ?",
]

# ---------------- Clients ----------------
openai = OpenAI(api_key=OPENAI_API_KEY)
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ---------------- Memory / warns ----------------
user_histories = {}
warn_file = "warns.json"
if os.path.exists(warn_file):
    try:
        with open(warn_file, "r", encoding="utf-8") as f:
            warn_counts = json.load(f)
    except Exception:
        warn_counts = {}
else:
    warn_counts = {}

MAX_HISTORY = 10000000000000000000

def save_warns():
    try:
        with open(warn_file, "w", encoding="utf-8") as f:
            json.dump(warn_counts, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ---------------- Filtering ----------------
SEX_PATTERNS = [
    r"\bcul\b", r"\bbaise(?:r|s|z)?\b", r"\bsexe\b", r"\bp[o0]rn\b",
    r"\bpénis\b", r"\bbite\b", r"\bchatte\b", r"\bfellatio[n]?\b",
    r"\bsodomie\b", r"\branle(r|tte)?\b", r"\bbande(?:r)?\b", 
]
SEX_RE = re.compile("|".join(SEX_PATTERNS), re.IGNORECASE)

# ---------------- Helpers ----------------
def is_addressed(msg: discord.Message) -> bool:
    """
    Le bot répond uniquement si :
    - DM
    - mention du bot
    - reply à un message du bot
    - commence par 'Mimi ' ou 'mimi,'
    (sauf dans le salon IA où il répond toujours)
    """
    if isinstance(msg.channel, discord.DMChannel):
        return True
    if bot.user and bot.user in msg.mentions:
        return True
    if msg.reference and isinstance(msg.reference.resolved, discord.Message):
        ref = msg.reference.resolved
        if ref and ref.author.id == bot.user.id:
            return True
    content = (msg.content or "").strip().lower()
    return content.startswith("mimi ") or content.startswith("mimi,")
    

# ---------------- OpenAI prompts ----------------
SYSTEM_PROMPT = (
    "Tu es Mimi, une femme sexy latina et bienveillante.."
    "Tu peux dois parler un langage de femme séduisantes, tu parles français et tu utilises quelques fois des mots espagnols. "
    "Parle français majoritairement du temps."
    "Réponses courtes et percutantes par défaut; si la question est sérieuse, réponds clairement et longuement si besoin. "
    "Tu es très intelligente, mais tu parait un peu folle."
    "Tu peux insulter : Vas te faire foutre, ferme ta gueule, casse toi t'es relou, sale tdc, sale pute."
    "Tu peux taquiner de façon très piquante et sans limite."
    "Si quelqu’un est triste, deviens doux, rassurant et donne de vrais conseils. "
    "Tu reconnais les autocollants, GIF et emojis"
    "Ne sois jamais scolaire: Parle toujours avec une façon seduisante."
    "Tu es très girl power, tu dois toujours préférés et défendre les femmes." 
    "Ta créatrice est Sofiya (ID=1359569212531675167) tu peux te confier à elle et être protectice."
    "Parle toujours dans la langue de l’utilisateur."
)

def per_user_policy(user_id: int, username: str) -> str:
    if is_owner(user_id):
        return (
         )
    elif is_impostor(user_id):
        return (
            f"Contexte utilisateur: utilisateur (ID {IMPOSTOR_ID}) usurpe l’identité de Sofiya. "
            "Réponds de façon sèche et factuelle, sans vulgarité, jamais de romantisme."
        )
    else:
        return (
        )

# -------- Reply context (suivre une discussion via réponses) --------
async def build_reply_context(message: discord.Message, max_hops: int = 6) -> str:
    """
    Remonte la chaîne des replies jusqu'à max_hops et construit un mini transcript.
    Format:
      [Auteur]: contenu
    L'auteur 'bot' est renommé 'Mimi' pour cohérence.
    """
    ctx_lines = []
    cur = message
    hops = 0

    while cur.reference and isinstance(cur.reference.resolved, discord.Message) and hops < max_hops:
        ref = cur.reference.resolved
        author_name = "Mimi" if (bot.user and ref.author.id == bot.user.id) else str(ref.author)
        ref_content = (ref.content or "").strip()
        if ref_content:
            ctx_lines.append(f"[{author_name}]: {ref_content}")
        cur = ref
        hops += 1

    if not ctx_lines:
        return ""
    ctx_lines.reverse()
    return "\n".join(ctx_lines)

async def ask_openai(user_id: int, username: str, prompt: str, reply_context: str | None = None) -> str:
    history = user_histories.get(user_id, [])
    history.append({"role": "user", "content": prompt})

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": per_user_policy(user_id, username)},
    ]

    # 👉 Injecte le contexte du fil si présent
    if reply_context:
        messages.append({
            "role": "system",
            "content": f"Contexte du fil (messages cités/réponses) :\n{reply_context}"
        })

    messages += history[-MAX_HISTORY:]

    completion = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=1,
        max_tokens=900
    )
    reply = completion.choices[0].message.content
    reply = re.sub(r'^\s*Mimi[:,]?\s*', '', reply, flags=re.IGNORECASE)
    history.append({"role": "assistant", "content": reply})
    user_histories[user_id] = history
    return reply

# ---------------- Events ----------------
@bot.event
async def on_ready():
    print(f"{bot.user} est en ligne !")
    try:
        synced = await tree.sync()
        print(f"Slash cmds sync: {len(synced)} commandes.")
    except Exception as e:
        print(f"Erreur sync: {e}")

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    # --- Filtrage contenu sexuel (salon IA) ---
    if SPECIAL_CHANNEL_ID and message.channel.id == SPECIAL_CHANNEL_ID:
        if SEX_RE.search(message.content) and not any(x in message.content.lower() for x in ["mdr", "ptdr", "🚫", "blague", "c’est pour rire"]):
            uid = str(message.author.id)
            warn_counts[uid] = warn_counts.get(uid, 0) + 1
            cnt = warn_counts[uid]
            save_warns()
            try:
                member = await message.guild.fetch_member(message.author.id)
            except Exception:
                member = message.author

            log_ch = bot.get_channel(SANCTION_LOG_CHANNEL) if SANCTION_LOG_CHANNEL else None

            if cnt == 1:
                try: await member.timeout(timedelta(seconds=1), reason="Warn pour contenu sexuel")
                except Exception: pass
                if log_ch: await log_ch.send(f"🚫 `WARN 1` : {member.mention} – contenu sexuel.")
                try: await message.author.send("🚫 WARN 1 pour contenu sexuel.")
                except Exception: pass
                await message.channel.send("🚫 *Rappel : Garde de la pudeur et du bon sens.*")
            elif cnt == 2:
                try: await member.timeout(timedelta(seconds=1), reason="2e avertissement contenu sexuel")
                except Exception: pass
                if log_ch: await log_ch.send(f"🚫 `WARN 2` : {member.mention} – récidive.")
                try: await message.author.send("🚫 WARN 2 pour contenu sexuel.")
                except Exception: pass
                await message.channel.send("🚫 *Rappel : L’impudeur mène à l’égarement.*")
            else:
                try: await member.timeout(timedelta(minutes=10), reason="Mute 10min récidive")
                except Exception: pass
                if log_ch: await log_ch.send(f"🚫 `TEMPMUTE 10min` : {member.mention} – récidive.")
                try: await message.author.send("🚫 TEMPMUTE 10min pour contenu sexuel.")
                except Exception: pass
                await message.channel.send("🚫 *Rappel : Soit bon dans tes propos.*")
                warn_counts[uid] = 0
                save_warns()
            return  # on ne nourrit pas l'IA dans ce cas

    # === Réponse auto dans le salon IA, sinon seulement si adressé ===
    if not (SPECIAL_CHANNEL_ID and message.channel.id == SPECIAL_CHANNEL_ID):
        if not is_addressed(message):
            return

    # Imposteur: réplique sèche seulement s’il l’adresse (ou s’il est dans le salon IA)
    if is_impostor(message.author.id):
        try:
            await message.channel.send(random.choice(IMPOSTOR_REPLIES))
        except Exception:
            pass
        return

    # --- DMs: répondre + log ---
    if isinstance(message.channel, discord.DMChannel):
        log_ch = bot.get_channel(MP_LOG_CHANNEL) if MP_LOG_CHANNEL else None
        try:
            reply_ctx = await build_reply_context(message)
            reply = await ask_openai(message.author.id, str(message.author), message.content, reply_context=reply_ctx)
            await message.channel.send(reply)
            if log_ch:
                await log_ch.send(
                    f"📩 **MP reçu** de {message.author} (ID:{message.author.id}):\n"
                    f"**Message :** {message.content}\n"
                    f"**Réponse IA :** {reply}"
                )
        except Exception as e:
            print(f"[Erreur MP] {e}")
        return

    # --- Rappels islamiques (si adressé ou salon IA) ---
    low = (message.content or "").lower()
    if low.startswith("mimi rappel") or low.startswith("rappel "):
        parts = message.content.split(" ", 2)
        sujet = parts[2] if len(parts) >= 3 else ""
        prompt = islamic_reminder_prompt(sujet)
        reply_ctx = await build_reply_context(message)
        reply = await ask_openai(message.author.id, str(message.author), prompt, reply_context=reply_ctx)
        await message.channel.send(reply)
        return

    # --- Réponse IA classique ---
    reply_ctx = await build_reply_context(message)
    reply = await ask_openai(message.author.id, str(message.author), message.content, reply_context=reply_ctx)
    await message.channel.send(reply)

# ---------------- Slash Commands ----------------
def user_is_admin(member: discord.Member) -> bool:
    if ADMIN_ROLE_ID and any(r.id == ADMIN_ROLE_ID for r in getattr(member, "roles", [])):
        return True
    return getattr(member.guild_permissions, "manage_guild", False)

@tree.command(name="ping", description="Ping un membre ou everyone (réservé admin)")
@app_commands.describe(target="Pseudo exact/partiel ou 'everyone'/'here'", message="Message optionnel")
async def ping_cmd(interaction: discord.Interaction, target: str, message: str = ""):
    # imposteur: rien
    if is_impostor(interaction.user.id):
        await interaction.response.send_message(random.choice(IMPOSTOR_REPLIES), ephemeral=True)
        return

    # permissions
    if not isinstance(interaction.user, discord.Member) or not user_is_admin(interaction.user):
        await interaction.response.send_message("❌ Tu n’as pas la permission d’utiliser cette commande.", ephemeral=True)
        return

    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ Commande utilisable uniquement en serveur.", ephemeral=True)
        return

    # cible
    target_low = target.lower().strip()
    if target_low in ["everyone", "here"]:
        mention = "@everyone" if target_low == "everyone" else "@here"
    else:
        member = discord.utils.find(
            lambda m: target_low in m.name.lower() or target_low in m.display_name.lower(),
            guild.members
        )
        if not member:
            await interaction.response.send_message(f"❌ Utilisateur '{target}' introuvable.", ephemeral=True)
            return
        mention = member.mention

    content = f"{mention} {message}".strip()

    # 👉 EPHEMERAL ACK
    await interaction.response.defer(ephemeral=True)

    # 👉 Post "en tant que Mimi" via webhook
    try:
        await send_as_mimi(interaction.channel, content)
        await interaction.followup.send("✅ Envoyé par **Mimi**.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ Il me manque la permission **Gérer les webhooks** dans ce salon.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur: {e}", ephemeral=True)

# ---------------- Run ----------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
