c------------------------------------------------------------------------
c     Unterroutine zur Det-Best. von 2x2-Matrizen
c     EIN: m(2,2)
c     AUS: det22
c
c     RaM 1996

      real*8 function det22(m)

      real*8 m(2,2)

      det22=m(1,1)*m(2,2)-m(1,2)*m(2,1)

      end
c------------------------------------------------------------------------
c     Unterroutine zur Det-Best. von 3x3-Matrizen
c     EIN: m(3,3)
c     AUS: det33
c
c     RaM 1996

      real*8 function det33(m)

      real*8 m(3,3)

      det33=m(1,1)*m(2,2)*m(3,3)+m(1,2)*m(2,3)*m(3,1)
     x     +m(2,1)*m(3,2)*m(1,3)-m(1,3)*m(2,2)*m(3,1)
     x     -m(2,3)*m(1,1)*m(3,2)-m(1,2)*m(3,3)*m(2,1)

      end
c----------------------------------------------------------------------
c     Unterroutine zur Best. der Inv. einer 2x2-Matrix
c     EIN: m(2,2)
c     AUS: im(2,2)
c
c     RaM 1995

      subroutine invmat22(m,im)

      real*8 m(2,2),im(2,2)
      real*8 det,det22

      det=det22(m)

      im(1,1)=+m(2,2)/det
      im(1,2)=-m(1,2)/det

      im(2,1)=-m(2,1)/det
      im(2,2)=+m(1,1)/det

      end
c----------------------------------------------------------------------
c     Unterroutine zur Best. der Inv. einer 3x3-Matrix
c     EIN: m(3,3)
c     AUS: im(3,3)
c
c     RaM 1995

      subroutine invmat33(m,im)

      real*8 m(3,3),im(3,3)
      real*8 det,det33

      det=det33(m)

      im(1,1)=(m(2,2)*m(3,3)-m(2,3)*m(3,2))/det
      im(1,2)=(m(1,3)*m(3,2)-m(1,2)*m(3,3))/det
      im(1,3)=(m(1,2)*m(2,3)-m(1,3)*m(2,2))/det

      im(2,1)=(m(2,3)*m(3,1)-m(2,1)*m(3,3))/det
      im(2,2)=(m(1,1)*m(3,3)-m(1,3)*m(3,1))/det
      im(2,3)=(m(1,3)*m(2,1)-m(1,1)*m(2,3))/det

      im(3,1)=(m(2,1)*m(3,2)-m(2,2)*m(3,1))/det
      im(3,2)=(m(1,2)*m(3,1)-m(1,1)*m(3,2))/det
      im(3,3)=(m(1,1)*m(2,2)-m(1,2)*m(2,1))/det

      end
c----------------------------------------------------------------------
c     Unterroutine zur Add. zweier 3x3 Matrizen
c     EIN: a(3,3),b(3,3)
c     AUS: c(3,3)
c
c     RaM 1996

      subroutine addmat33(a,b,c)

      real*8 a(3,3),b(3,3)
      real*8 c(3,3)
      integer i,j

      do 100 i=1,3
	do 110 j=1,3
	  c(i,j)=a(i,j)+b(i,j)
110     continue
100   continue

      end
c----------------------------------------------------------------------
c     Unterroutine zur Multi. zweier 3x3 Matrizen
c     EIN: a(3,3),b(3,3)
c     AUS: c(3,3)
c
c     RaM 1996

      subroutine mulmat33(a,b,c)

      real*8 a(3,3),b(3,3)
      real*8 c(3,3)
      integer i,j,k

      do 130 i=1,3
	do 140 j=1,3
	  c(i,j)=0.d0
	  do 150 k=1,3
	    c(i,j)=c(i,j)+a(i,k)*b(k,j)
150       continue
140     continue
130   continue

      end
c----------------------------------------------------------------------
c     Unterroutine zur Add. zweier 6x6 Matrizen
c     EIN: a(6,6),b(6,6)
c     AUS: c(6,6)
c
c     RaM 1996

      subroutine addmat66(a,b,c)

      real*8 a(6,6),b(6,6)
      real*8 c(6,6)
      integer i,j

      do 100 i=1,6
	do 110 j=1,6
	  c(i,j)=a(i,j)+b(i,j)
110     continue
100   continue

      end
c----------------------------------------------------------------------
c     Unterroutine zur Multi. zweier 6x6 Matrizen
c     EIN: a(6,6),b(6,6)
c     AUS: c(6,6)
c
c     RaM 1996

      subroutine mulmat66(a,b,c)

      real*8 a(6,6),b(6,6)
      real*8 c(6,6)
      integer i,j,k

      do 130 i=1,6
	do 140 j=1,6
	  c(i,j)=0.d0
	  do 150 k=1,6
	    c(i,j)=c(i,j)+a(i,k)*b(k,j)
150       continue
140     continue
130   continue

      end
c----------------------------------------------------------------------
c     Funktion fuer Skalarprodukt zweier 3-Vektoren
c
c     EIN a(3),b(3)
c
c     RaM 1996

      real*8 function dot3(a,b)

      real*8 a(3),b(3)

      dot3=a(1)*b(1)+a(2)*b(2)+a(3)*b(3)

      end
c----------------------------------------------------------------------
c     Funktion fuer Skalarprodukt zweier 6-Vektoren
c
c     EIN a(6),b(6)
c
c     RaM 1996

      real*8 function dot6(a,b)

      real*8 a(6),b(6)

      dot6=a(1)*b(1)+a(2)*b(2)+a(3)*b(3)
     x    +a(4)*b(4)+a(5)*b(5)+a(6)*b(6)

      end
c----------------------------------------------------------------------
c     Unterroutine fuer Kreuzprodukt zweier 3-Vektoren
c     EIN a(3),b(3)
c
c     AUS c(3)
c
c     RaM 1996

      subroutine cross3(a,b,c)

      real*8 a(3),b(3)
      real*8 c(3)

      c(1)=a(2)*b(3)-b(2)*a(3)
      c(2)=a(3)*b(1)-b(3)*a(1)
      c(3)=a(1)*b(2)-b(1)*a(2)

      end
c----------------------------------------------------------------------
c     Funktion fuer Betrag eines 3-Vektors
c
c     EIN a(3),
c
c     RaM 1996

      real*8 function abs3(a)

      real*8 a(3)

      abs3=dsqrt(a(1)*a(1)+a(2)*a(2)+a(3)*a(3))

      end
c----------------------------------------------------------------------
c     Unterroutine zur Normierung eines 3-Vektors
c
c     EIN a(3)
c
c     AUS a(3)
c
c     RaM 1996

      subroutine norm3(a)

      real*8 a(3)
      real*8 c,abs3     
 
      c=abs3(a)

      a(1)=a(1)/c
      a(2)=a(2)/c
      a(3)=a(3)/c

      end
c----------------------------------------------------------------------
c     Unterrotuine zum Nullen einer Matrix
c
c     EIN m,imax,jmax,idim,jdim
c
c     AUS m
c
c     RaM 1996

      subroutine zeromat(m,imax,jmax,idim,jdim)

      real*8 m(idim,jdim)
      integer i,j,imax,jmax,idim,jdim

      do 150 i=1,imax
	do 160 j=1,jmax
	  m(i,j)=0.d0
160     continue
150   continue

      end
c----------------------------------------------------------------------
c     Unterrotuine zum Nullen eines Vektors
c
c     EIN v,imax,idim
c
c     AUS v
c
c     RaM 1996

      subroutine zerovec(v,imax,idim)

      real*8 v(idim)
      integer i,imax,idim

      do 170 i=1,imax
	v(i)=0.d0
170   continue

      end
c----------------------------------------------------------------------
c     Unterroutuine zum Ausgeben einer Matrix
c
c     EIN m,imax,jmax,idim,jdim
c
c     AUS m
c
c     RaM 1996

      subroutine printmat(m,imax,jmax,idim,jdim)

      real*8 m(idim,jdim)
      integer i,j,imax,jmax,idim,jdim

      do 200 i=1,imax
	print '(1000e14.5)',(m(i,j),j=1,jmax)
200   continue

      end
c-----------------------------------------------------------------------
c     Unterroutine zum Anhalten eines Programs
c
c     RaM 1996

      subroutine weiter

      character halt

      print*,' '
      print*,' Weiter mit [RETURN] , Anhalten mit [Q] !!!'
      print*,' '

      read(*,'(a)') halt

      if((halt.eq.'Q').or.(halt.eq.'q')) STOP

      end
c------------------------------------------------------------------------
c     Unterroutine zum Anzeigen des Fortschritts eines Vorgangs
c
c     EIN aktuell,ende
c
c     RaM

      subroutine progress(aktuell,ende)

      integer aktuell,ende

      integer pro,alt,diff,i

      save alt

      pro=20*aktuell/ende

      diff=pro-alt
      alt=pro
      do 100 i=1,diff
	print '(a,$)','.'
100   continue

      if(pro.eq.20) then
	alt=0
	print*,' '
      endif

      end
c------------------------------------------------------------------------
c     Unterroutine zum Anzeigen des Fortschritts eines Vorgangs
c
c     EIN aktuell,ende
c
c     RaM

      subroutine progress_pro(aktuell,ende)

      integer aktuell,ende

      integer pro,alt,diff,i
      logical skala

      save alt,skala

      if((alt.eq.0).and.(skala.eqv..false.)) then
        skala=.true.
	print '(a)','0%       50%       100%'
	print '(a)','+----+----+----+----+'
      endif

      pro=20*aktuell/ende

      diff=pro-alt
      alt=pro
      do 100 i=1,diff
	print '(a,$)','.'
100   continue

      if(pro.eq.20) then
	alt=0
	print*,' '
        skala=.false.
      endif

      end
c------------------------------------------------------------------------
c     Unterroutine zum Anzeigen der Meldung, dass etwas noch nicht
c     implementiert wurde
c
c     RaM

      subroutine implement

      character taste

      print*,' '
      print*,' > > > > > NOCH NICHT IMPLEMENTIERT < < < < <'
      print*,' '
      read '(a1)',taste

      end
c------------------------------------------------------------------------
