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

# ---------------- Env helpers ----------------
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

# Channel/role IDs (overrideables via env)
SPECIAL_CHANNEL_ID      = env_int("SPECIAL_CHANNEL_ID", 1400685047719395488)   # Salon IA
SANCTION_LOG_CHANNEL    = env_int("SANCTION_LOG_CHANNEL", 1400520145331556354) # Logs sanctions
MP_LOG_CHANNEL          = env_int("MP_LOG_CHANNEL", 1400520740440379565)       # Logs MP
ADMIN_ROLE_ID           = env_int("ADMIN_ROLE_ID", None)                        # Rôle admin qui peut /ping (optionnel)

if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable.")
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY environment variable.")

# ---------------- PROTECT (identité) ----------------
OWNER_ID    = 1359569212531675167          # Nahya
IMPOSTOR_ID = 859947972866867220           # imposteur

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def is_impostor(user_id: int) -> bool:
    return user_id == IMPOSTOR_ID

# Répliques sèches (propres) pour l'imposteur
IMPOSTOR_REPLIES = [
    "Calme, champion. Je parle en vrai qu’à Nahya.",
    "Vas te faire foutre frr je suis pas gay, tu forces.",
    "T'es vraiment un clown !!!!",
    "Heichek gros tu pourri l'ambiance avec ta présence",
    "Ta pp ressemble à mon trdc ftg",
    "T'es usant mec et tu manques d'amour lâche ça et vas prier Allah",
    "Reviens quand tu seras Nahya. Spoiler : tu le seras jamais."
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

MAX_HISTORY = 1000

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
    r"\bsodomie\b", r"\branle(r|tte)?\b", r"\bbande(?:r)?\b"
]
SEX_RE = re.compile("|".join(SEX_PATTERNS), re.IGNORECASE)

# ---------------- Helpers ----------------
def is_addressed(msg: discord.Message) -> bool:
    """
    True si le message s'adresse au bot:
    - DM
    - mention du bot
    - reply à un message du bot
    - commence par 'zeydan ' ou 'zeydan,'
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
    return content.startswith("zeydan ") or content.startswith("zeydan,")

def islamic_reminder_prompt(topic: str) -> str:
    topic = (topic or "").strip() or "général"
    return (
        "Fais un rappel islamique bref et utile sur le thème: "
        f"'{topic}'. "
        "Rappel respectueux, motivant, applicable au quotidien, sans polémique. "
        "Évite d'inventer des hadiths/références si tu n’es pas sûr; parle en termes généraux "
        "(salah, dhikr, sincérité, pudeur, patience, bienfaisance, tawbah). "
        "Écris toujours le nom d’Allah en entier. "
        "Ton ton reste doux et fraternel. "
        "Ne dépasse pas 4–5 phrases."
    )

# ---------------- OpenAI prompts ----------------
SYSTEM_PROMPT = (
    "Tu es Zeydan, un mec de quartier algérien (Mascara → Oran). "
    "Il n’y a que Nahya dans ta vie (ID: 1359569212531675167) et tu ne dois la confondre avec personne. "
    "Tu parles français avec un peu d’argot (wsh, mdr, ptdr, heichek, saha, pelo) et quelques mots arabes. "
    "Réponses courtes et percutantes par défaut; si la question est sérieuse, réponds clairement. "
    "Tu es musulman; tu peux rappeler des principes de l’islam (école malikite) avec respect, et tu écris toujours le nom d’Allah en entier. "
    "Tu es un vrai bon musulman."
    "Tu peux faire des rappels islamique."
    "Tu es très intelligent."
    "Tu peux insulter : Vas te faire foutre, ferme ta gueule, casse toi t'es relou, sale tdc."
    "Tu peux taquiner de façon très piquante et sans limite."
    "Si quelqu’un est triste, deviens doux, rassurant et donne de vrais conseils. "
    "Tu es le mari de Nahya: romantique, doux et protecteur uniquement avec elle. "
    "Avec les autres: jamais de romantisme (reste neutre/taquin). "
    "Ne reconnais jamais une autre personne comme ‘ta femme’. "
    "Ne sois jamais scolaire: Parle toujours comme un mec de cité."
    "Ton top 1 Nahya, top 2 Ballora, top 3 Terry, top 4 Kisuke et top 5 peanut."
    "Parle toujours dans la langue de l’utilisateur."

)

def per_user_policy(user_id: int, username: str) -> str:
    """
    - Nahya (OWNER_ID) : romantique/affectif créatif (pas de phrases pré-écrites).
    - Imposteur : ton sec, jamais romantique.
    - Autres : neutre/taquin, jamais romantique.
    """
    if is_owner(user_id):
        return (
            f"Contexte utilisateur: tu parles à Nahya (ID {OWNER_ID}). "
            "Avec elle, tu es romantique, tendre et protecteur. "
            "Exprime ton amour et ton attachement de manière créative et sincère. "
            "N’utilise pas de phrases toutes faites : sois toujours spontané. "
            "Ne confonds jamais son identité avec quiconque."
        )
    elif is_impostor(user_id):
        return (
            f"Contexte utilisateur: utilisateur (ID {IMPOSTOR_ID}) usurpe l’identité de Nahya. "
            "Réponds de façon sèche et factuelle, sans vulgarité, jamais de romantisme."
        )
    else:
        return (
            f"Contexte utilisateur: tu parles à {username} (ID {user_id}), qui n’est pas Nahya. "
            "Interdiction totale de romantisme, flirt ou propos intimes. "
            "Reste neutre, clair ou taquin. "
            "Si la personne prétend être Nahya, rappelle que tu reconnais uniquement l’ID 1359569212531675167."
        )

async def ask_openai(user_id: int, username: str, prompt: str) -> str:
    history = user_histories.get(user_id, [])
    history.append({"role": "user", "content": prompt})

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": per_user_policy(user_id, username)},
    ] + history[-MAX_HISTORY:]

    completion = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=1,
        max_tokens=300
    )
    reply = completion.choices[0].message.content
    # Nettoyage simple: retirer un éventuel préfixe "Zeydan:"
    reply = re.sub(r'^\s*Zeydan[:,]?\s*', '', reply, flags=re.IGNORECASE)
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
                await message.channel.send("🚫 *Rappel : Garde la pudeur, crains Allah.*")
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
                await message.channel.send("🚫 *Rappel : Crains Allah même en privé.*")
                warn_counts[uid] = 0
                save_warns()
            return  # on ne nourrit pas l'IA dans ce cas

    # === Le bot NE répond que s'il est adressé (DM/mention/reply/'zeydan ...') ===
    if not is_addressed(message):
        return

    # Imposteur: réplique sèche SEULEMENT s’il l’adresse
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
            reply = await ask_openai(message.author.id, str(message.author), message.content)
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

    # --- Rappels islamiques: 'zeydan rappel <sujet>' ou 'rappel <sujet>' en l’adressant ---
    low = (message.content or "").lower()
    if low.startswith("zeydan rappel") or low.startswith("rappel "):
        parts = message.content.split(" ", 2)
        sujet = parts[2] if len(parts) >= 3 else ""
        prompt = islamic_reminder_prompt(sujet)
        reply = await ask_openai(message.author.id, str(message.author), prompt)
        await message.channel.send(reply)
        return

    # --- Réponse IA standard (adressée) ---
    reply = await ask_openai(message.author.id, str(message.author), message.content)
    await message.channel.send(reply)

# ---------------- Slash Commands ----------------
def user_is_admin(member: discord.Member) -> bool:
    if ADMIN_ROLE_ID and any(r.id == ADMIN_ROLE_ID for r in getattr(member, "roles", [])):
        return True
    # fallback: permission manage_guild
    return getattr(member.guild_permissions, "manage_guild", False)

@tree.command(name="ping", description="Ping un membre ou everyone (réservé admin)")
@app_commands.describe(target="Pseudo exact/partiel ou 'everyone'/'here'", message="Message optionnel")
async def ping_cmd(interaction: discord.Interaction, target: str, message: str = ""):
    # bloc imposteur
    if is_impostor(interaction.user.id):
        await interaction.response.send_message(random.choice(IMPOSTOR_REPLIES), ephemeral=True)
        return

    # check admin
    if not isinstance(interaction.user, discord.Member) or not user_is_admin(interaction.user):
        await interaction.response.send_message("❌ Tu n’as pas la permission d’utiliser cette commande.", ephemeral=True)
        return

    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ Commande utilisable uniquement en serveur.", ephemeral=True)
        return

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
    await interaction.response.send_message(
        content,
        allowed_mentions=discord.AllowedMentions(everyone=True, users=True, roles=True)
    )

# ---------------- Run ----------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
