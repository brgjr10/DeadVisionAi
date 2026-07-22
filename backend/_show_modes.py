import pathlib
p=pathlib.Path(r'F:/DeadVisionAi/backend/app/gateway/router.py')
src=p.read_text('utf-8')
print(len(src),'chars')
print(type(src))
print(src[:100])
