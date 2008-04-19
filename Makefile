
all: deb

REPO=$(HOME)/tekstit/web/txt/repo

deb:
	dpkg-buildpackage -rfakeroot -b 
	mkdir -p dist/deb
	mv ../gutenbrowse_* dist/deb

repo:
	cp dist/deb/gutenbrowse_*.deb $(REPO)/pool/bora
	cp dist/deb/gutenbrowse_*.deb $(REPO)/pool/chinook
	cp gutenbrowse.install $(REPO)/singleclick

