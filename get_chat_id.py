import requests

TOKEN = "p0xElos8IqanPupfgm2BEvtftrcR5bOGqkCYs-z8W0U"


resp = requests.get(
    "https://api.pachca.com/api/shared/v1/messages",
    headers={"Authorization": f"Bearer {TOKEN}"},
    params={
        "chat_id": 34550358, # 34550358
        "per": 5
    }
)

print("Статус:", resp.status_code)
print("Ответ:", resp.text[:1000])
