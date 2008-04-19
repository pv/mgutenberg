
all: deb

deb:
	dpkg-buildpackage -rfakeroot -b 
	mkdir -p dist/deb
	mv ../gutenbrowse_* dist/deb

repo:
	cp dist/deb/gutenbrowse_*.deb \
		$(HOME)/tekstit/web/txt/repo/pool/bora
	cp dist/deb/gutenbrowse_*.deb \
		$(HOME)/tekstit/web/txt/repo/pool/chinook
