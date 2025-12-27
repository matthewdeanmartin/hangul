install:
	uv sync

convert:
	pyftsubset "./noto-sans-kr/Noto_Sans_KR/NotoSansKR-Regular.otf" --output-file="./noto-sans-kr/Noto_Sans_KR/NotoSansKR-Regular.ttf" --flavor=ttf

run:
	export FONT_PATH=./noto-sans-kr/Noto_Sans_KR
	hangul