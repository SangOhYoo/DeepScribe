import datetime

timestamps = [
    (1780123385, "initial"),
    (1780123388, "rename"),
    (1780125091, "feat: automatically generate world setting"),
    (1780125198, "feat: enhance AI theme"),
    (1780125249, "feat: enhance AI overall plot"),
    (1780125542, "fix: URL-encode asset"),
    (1780128683, "fix: fully URL-encode"),
    (1780141078, "Fix asset preview thumbnails"),
    (1780198747, "feat: implement divide-and-conquer"),
    (1780754710, "Fix scenario node title sync"),
    (1780847875, "feat: 캐릭터 설정 전용 탭 분리")
]

print("Timestamps in KST:")
for ts, msg in timestamps:
    dt = datetime.datetime.fromtimestamp(ts, datetime.timezone(datetime.timedelta(hours=9)))
    print(f"{ts} -> {dt.isoformat()} : {msg}")
