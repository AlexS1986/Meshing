# Makefile for program systems

# Dependencies (extensions)
.SUFFIXES: .o .f

# Object modules
OBJ = trafo.o matfunc.o dgedi.o dgesubs.o dgefa.o

# Dependency for the executable file *.x
trafo.x: $(OBJ)
	gfortran -o $@ $(OBJ)
	touch $@

# Specific dependencies for individual files
trafo.o: trafo.f
matfunc.o: matfunc.f
dgefa.o: dgefa.f
dgedi.o: dgedi.f
dgesubs.o: dgesubs.f

# What to do when *.o is older than *.f
.f.o:
	gfortran -c -O $<
	touch $*.o

