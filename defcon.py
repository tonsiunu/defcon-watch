import os
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode import SocketModeHandler
import requests
import aiohttp
import asyncio
from fpl import FPL
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

teams = ["", "Arsenal ", "Aston Villa ", "Burnley ", "Bournemouth ", "Brentford ", "Brighton ", "Chelsea ", "C Palace ", "Everton ", "Fulham ", "Leeds ", "Liverpool ", "Man City ", "Man Utd ", "Newcastle ", "Nottm Forest ", "Sunderland ", "Spurs ", "West Ham ", "Wolves "]
emotes = ["", "🔴 ", "🦁 ", "🟣 ", "🍒 ", "🐝 ", "🕊️ ", "🔵 ", "🦅 ", "🍬 ", "🏡 ", "🏵️ ", "🐦 ", "⛵ ", "😈 ", "⚫ ", "🌳 ", "🐈‍⬛ ", "⚪ ", "⚒️ ", "🐺 "]
channel_name = "#matchdaylive"

app = AsyncApp(token="REDACTED")

async def loop(app):
    async with aiohttp.ClientSession() as session:
        fpl = FPL(session)
        players = await fpl.get_players()
        players.sort(key=lambda x: x.id)
        defcons = [0 for _ in range(len(players) + 1)]
        finished_games = set()
        bonus_sent = set()
        cont = requests.get("https://fantasy.premierleague.com/api/fixtures/").json()
        
        for fix in cont:
            if fix["finished"]:
                finished_games.add(fix["id"])
                bonus_sent.add(fix["id"])
            
        half_sent = set()
        near_sent = set()
        done_sent = set()

        # await app.client.chat_postMessage(channel=channel_name, text="DEFCON Watch is now running")

        while True:
            try:
                cont = requests.get("https://fantasy.premierleague.com/api/fixtures/?event=12").json()
            except Exception:
                print("connection error")
                await asyncio.sleep(5)
                continue
            
            fix_num = 0

            for fix in cont:
                if fix["started"] and not fix["finished_provisional"]:
                    fix_num += 1

                if fix["started"] and not fix["finished"]: # get defcons for non-finished games
                    for stat in fix["stats"]:
                        if stat["identifier"] == "defensive_contribution":
                            for player in stat["a"] + stat["h"]:
                                defcons[player["element"]] = player["value"]

                elif fix["finished"] and fix["id"] not in finished_games: # reset defcons for finished games
                    finished_games.add(fix["id"])
                    home = int(fix["team_h"])
                    away = int(fix["team_a"])
                    for p in players:
                        if p.team in [home, away]:
                            defcons[p.id] = 0
                            if p.id in half_sent:
                                half_sent.remove(p.id)
                            if p.id in near_sent:
                                near_sent.remove(p.id)
                            if p.id in done_sent:
                                done_sent.remove(p.id)

                if fix["finished_provisional"] and not fix["finished"] and fix["id"] not in bonus_sent: # send bonus
                    fpl_fix = await fpl.get_fixture(fix["id"])
                    data = fpl_fix.get_bonus(provisional=True)
                    three = set()
                    two = set()
                    one = set()
                    for player in data["a"] + data["h"]:
                        if player["value"] == 3:
                            three.add(players[player["element"] - 1].web_name)
                        if player["value"] == 2:
                            two.add(players[player["element"] - 1].web_name)
                        if player["value"] == 1:
                            one.add(players[player["element"] - 1].web_name)
                    out = "Final: " + emotes[fix["team_h"]] + teams[fix["team_h"]] + str(fix["team_h_score"]) + "-" + str(fix["team_a_score"]) + " " + teams[fix["team_a"]] + emotes[fix["team_a"]] + "\nProvisional Bonus:"
                    if three:
                        out += "\n3 - " + ", ".join(three)
                    if two:
                        out += "\n2 - " + ", ".join(two)
                    if one:
                        out += "\n1 - " + ", ".join(one)
                    print(out)
                    await app.client.chat_postMessage(channel=channel_name, text=out)        
                    bonus_sent.add(fix["id"])
                     


            messages = []


            for i in range(1, len(defcons)):
                player = players[i - 1]
                suffix = "/10)" if player.element_type == 2 else "/12)"

                if (defcons[i] >= 10 and player.element_type == 2) or (defcons[i] >= 12 and player.element_type > 2):
                    if player.id not in done_sent:
                        done_sent.add(player.id)
                        near_sent.add(player.id)
                        half_sent.add(player.id)
                        messages.append(emotes[player.team] + player.web_name + " *has reached DEFCON*! (" + str(defcons[i]) + suffix)
                
                elif (defcons[i] >= 8 and player.element_type == 2) or (defcons[i] >= 10 and player.element_type > 2):
                    if player.id not in near_sent:
                        near_sent.add(player.id)
                        half_sent.add(player.id)
                        messages.append(emotes[player.team] + player.web_name + " is nearly at DEFCON! (" + str(defcons[i]) + suffix)

                elif ((defcons[i] >= 5 and player.element_type == 2) or (defcons[i] >= 6 and player.element_type > 2)) and fix_num == 1:
                    if player.id not in half_sent:
                        half_sent.add(player.id)
                        messages.append(emotes[player.team] + player.web_name + " is halfway to DEFCON! (" + str(defcons[i]) + suffix)

            if messages and len(messages) <= 5 and (len(messages) <= 2 or any(["reached" in x for x in messages])):
                print(messages)
                await app.client.chat_postMessage(channel=channel_name, text="\n".join(messages))        

            await asyncio.sleep(30)       



async def main():
    asyncio.create_task(loop(app))
    handler = AsyncSocketModeHandler(app, "REDACTED")
    await handler.start_async()

if __name__ == "__main__":
    asyncio.run(main())