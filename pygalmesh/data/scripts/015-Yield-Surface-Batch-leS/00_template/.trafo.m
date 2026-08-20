#Makefile fuer programmsysteme

#abhaengigkeiten (extensions)
.SUFFIXES:.o .f

#objekt-module
OBJ = trafo.o matfunc.o dgedi.o dgesubs.o dgefa.o

#abhaengigkeit der ausfuehrbaren datei *.x
trafo.x: $(OBJ)
	xlf -o $@ $(OBJ) 
	touch $@

#besondere abhaengigkeiten einzelner dateien
trafo.o: trafo.f
matfunc.o: matfunc.f
dgefa.o: dgefa.f
dgedi.o: dgedi.f
dgesubs.o: dgesubs.f

#was tun wenn *.o aelter *.f
.f.o:
	xlf -c -u -O $<
	touch $*.o
