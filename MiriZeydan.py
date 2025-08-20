import os
import re
import json
import random
import discord
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
SPECIAL_CHANNEL_ID   = env_int("SPECIAL_CHANNEL_ID", 1400685047719395488)   # Salon IA
SANCTION_LOG_CHANNEL = env_int("SANCTION_LOG_CHANNEL", 1400520145331556354) # Logs sanctions
AUTHORIZED_MENTION_ROLE = env_int("AUTHORIZED_MENTION_ROLE", 1400518143595778079)  # Rôle autorisé
MP_LOG_CHANNEL       = env_int("MP_LOG_CHANNEL", 1400520740440379565)       # Logs MP

if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable.")
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY environment variable.")

# ---------------- PROTECT (identité) ----------------
OWNER_ID = 1359569212531675167          # Nahya
IMPOSTOR_ID = 859947972866867220        # imposteur

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def is_impostor(user_id: int) -> bool:
    return user_id == IMPOSTOR_ID

# Répliques sèches (propre, sans insulte) pour l'imposteur
IMPOSTOR_REPLIES = [
    "Calme, champion. Je parle en vrai qu’à Nahya.",
    "Vas te faire foutre frr je suis pas gay, tu forces.",
    "T'es vraiment un clown !!!!",
    "T'es usant mec et tu manques d'amour lâche ça et vas prier Allah",
    "Reviens quand tu seras Nahya. Spoiler : tu le seras jamais."
]

# ---------------- Clients ----------------
client = discord.Client(intents=intents)
openai = OpenAI(api_key=OPENAI_API_KEY)

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

# ---------------- OpenAI helper ----------------
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
    Consigne stricte pour l’IA selon l’utilisateur courant.
    - Nahya (OWNER_ID) : romantique/affectif créatif (pas de phrases pré-écrites).
    - Imposteur : réplique sèche (gérée en code), jamais de romantisme.
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
            "Ne fournis aucune romance; si réponse, elle doit être sèche, factuelle, sans vulgarité."
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
@client.event
async def on_ready():
    print("Miri IA (Zeydan) est en ligne !")

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    # ==== PROTECT: imposteur -> réplique sèche puis stop
    if is_impostor(message.author.id):
        try:
            await message.channel.send(random.choice(IMPOSTOR_REPLIES))
        except Exception:
            pass
        return

    # --- DMs: répondre + log ---
    if isinstance(message.channel, discord.DMChannel):
        log_ch = client.get_channel(MP_LOG_CHANNEL) if MP_LOG_CHANNEL else None
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

    # --- Filtrage contenu sexuel dans le salon IA ---
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

            log_ch = client.get_channel(SANCTION_LOG_CHANNEL) if SANCTION_LOG_CHANNEL else None

            if cnt == 1:
                try:
                    await member.timeout(timedelta(seconds=1), reason="Warn pour contenu sexuel")
                except Exception:
                    pass
                if log_ch:
                    await log_ch.send(f"🚫 `WARN 1` : {member.mention} – contenu sexuel.")
                try:
                    await message.author.send("🚫 WARN 1 pour contenu sexuel.")
                except Exception:
                    pass
                await message.channel.send("🚫 *Rappel : Garde la pudeur, crains Allah.*")
            elif cnt == 2:
                try:
                    await member.timeout(timedelta(seconds=1), reason="2e avertissement contenu sexuel")
                except Exception:
                    pass
                if log_ch:
                    await log_ch.send(f"🚫 `WARN 2` : {member.mention} – récidive.")
                try:
                    await message.author.send("🚫 WARN 2 pour contenu sexuel.")
                except Exception:
                    pass
                await message.channel.send("🚫 *Rappel : L’impudeur mène à l’égarement.*")
            else:
                try:
                    await member.timeout(timedelta(minutes=10), reason="Mute 10min récidive")
                except Exception:
                    pass
                if log_ch:
                    await log_ch.send(f"🚫 `TEMPMUTE 10min` : {member.mention} – récidive.")
                try:
                    await message.author.send("🚫 TEMPMUTE 10min pour contenu sexuel.")
                except Exception:
                    pass
                await message.channel.send("🚫 *Rappel : Crains Allah même en privé.*")
                warn_counts[uid] = 0
                save_warns()
            return

    # --- Commandes ping autorisées ---
    if message.content.lower().startswith("zeydan ping "):
        if any(getattr(r, "id", None) == AUTHORIZED_MENTION_ROLE for r in getattr(message.author, "roles", [])):
            rest = message.content[len("zeydan ping "):]
            parts = rest.split(' ', 1)
            target = parts[0].lower()
            instr = parts[1] if len(parts) > 1 else ''

            if target in ['everyone', 'here']:
                mention = '@everyone' if target == 'everyone' else '@here'
            else:
                member = next((m for m in message.guild.members if m.name.lower() == target or m.display_name.lower() == target), None)
                if not member:
                    await message.channel.send(f"❌ Utilisateur '{target}' introuvable.")
                    return
                mention = member.mention

            if instr.lower().startswith('dis lui '):
                content = instr[len('dis lui '):]
            elif instr:
                prompt = f"Paraphrase de manière naturelle et stylée la phrase suivante pour {mention}, sans répéter mot à mot : '{instr}'"
                content = await ask_openai(message.author.id, str(message.author), prompt)
            else:
                prompt = f"Formule un message court et taquin pour {mention}, sans propos haineux ni insultes graves."
                content = await ask_openai(message.author.id, str(message.author), prompt)

            await message.channel.send(
                f"{mention} {content}".strip(),
                allowed_mentions=discord.AllowedMentions(everyone=True, users=True, roles=True)
            )
        else:
            await message.channel.send("Rôle non autorisé pour mentions.")
        return

    if message.content.lower().startswith('ping '):
        if any(getattr(r, "id", None) == AUTHORIZED_MENTION_ROLE for r in getattr(message.author, "roles", [])):
            pseudo = message.content[len('ping '):].strip().lower()
            member = next((m for m in message.guild.members if pseudo in m.name.lower() or pseudo in m.display_name.lower()), None)
            if member:
                await message.channel.send(f"{member.mention} {random.choice(['Répond !','On t’appelle !'])}")
        return

    # --- IA dans le salon IA ou si on mentionne le bot ---
    if (SPECIAL_CHANNEL_ID and message.channel.id != SPECIAL_CHANNEL_ID) and (client.user not in message.mentions):
        return

    # Réponse IA (avec policy par utilisateur)
    reply = await ask_openai(message.author.id, str(message.author), message.content)
    await message.channel.send(reply)

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
