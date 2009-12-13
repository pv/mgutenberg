
all: deb

REPO=$(HOME)/tekstit/web/txt/repo

deb:
	dpkg-buildpackage -rfakeroot -b 
	mkdir -p dist/deb
	mv ../mgutenberg_* dist/deb

repo:
	cp dist/deb/mgutenberg_*.deb $(REPO)/pool/bora
	cp dist/deb/mgutenberg_*.deb $(REPO)/pool/chinook
	cp mgutenberg.install $(REPO)/singleclick

