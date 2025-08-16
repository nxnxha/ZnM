# Déploiement sur Railway — MiriZeydan

## Étapes rapides
1. Crée un nouveau projet sur Railway (Empty Project).
2. Ajoute **ces 4 fichiers**: `MiriZeydan.py`, `requirements.txt`, `Procfile`, `README_Railway.md`.
3. Dans **Variables** sur Railway, ajoute:
   - `DISCORD_TOKEN` = ton token du bot Discord
   - `OPENAI_API_KEY` = ta clé OpenAI
   - (optionnel) `SPECIAL_CHANNEL_ID`, `SANCTION_LOG_CHANNEL`, `AUTHORIZED_MENTION_ROLE`, `MP_LOG_CHANNEL` (entiers)
4. Déploie. Dans les logs tu dois voir: `Miri IA est en ligne !`

## Permissions/Intents Discord
- Active **MESSAGE CONTENT INTENT** et **SERVER MEMBERS INTENT** dans le portail Discord (Bot → Privileged Gateway Intents).
- Invite le bot avec les permissions de modération si tu veux le `timeout` (Mute 10min).

## Stockage des warns
- Le fichier `warns.json` est écrit localement. Sur Railway, le système de fichiers peut être éphémère: en cas de redémarrage, les warns peuvent être perdus. Si tu veux les persister:
  - Ajoute un **Volume** dans Railway et monte-le à la racine de l’app, ou
  - Utilise une base externe (ex: Redis, PostgreSQL).

## Variables optionnelles (IDs)
Tu peux surcharger les IDs depuis Railway:
- `SPECIAL_CHANNEL_ID` — salon IA où l’IA répond par défaut et où le filtre s’applique
- `SANCTION_LOG_CHANNEL` — salon log des sanctions
- `AUTHORIZED_MENTION_ROLE` — rôle autorisé pour les pings spéciaux
- `MP_LOG_CHANNEL` — salon log des MP

## Commandes utiles
- Parler à l’IA dans le salon IA ou en mentionnant le bot.
- `zeydan ping <pseudo|everyone|here> <message>` — si l’auteur a le rôle autorisé.
- `ping <pseudo>` — ping court si rôle autorisé.

## Sécurité
- **Ne mets plus jamais tes tokens/clefs dans le code.** Utilise uniquement les variables d’environnement.
- Le persona a été ajusté pour rester piquant mais **sans propos haineux**.
