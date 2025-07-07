c-----7-----------------------------------------------------------------
      program trafo_main

c     INTERN
      real*8 cmat(6,6),smat(6,6),smatneu(6,6),hilf(6,6)
      real*8 tmate(6,6),tmats(6,6),itmats(6,6)
      real*8 phi1,phi2,amat(3,3),e(3),g(3),gmod,emod
      integer lmax,mmax,i,j,k,l,m
      
c     PARAMETER
      real*8 pi
      parameter(pi=3.14159265359d0)

c     DATEN
c      data cmat / 2.465d+5 , 1.473d+5 , 1.473d+5 , 0.d0 , 0.d0 , 0.d0 ,
c     x            1.473d+5 , 2.465d+5 , 1.473d+5 , 0.d0 , 0.d0 , 0.d0 ,
c     x            1.473d+5 , 1.473d+5 , 2.465d+5 , 0.d0 , 0.d0 , 0.d0 ,
c     x            0.d0 , 0.d0 , 0.d0 , 1.247d+5 , 0.d0, 0.d0 ,
c     x            0.d0 , 0.d0 , 0.d0 , 0.d0, 1.247d+5 , 0.d0 ,
c     x            0.d0 , 0.d0 , 0.d0 , 0.d0, 0.d0 , 1.247d+5 /
  
c      data cmat / 1.38d+1 , 4.00d-1 , 3.75d-1 , -2.89d-3 , 0.d0 , 0.d0 ,
c     x            4.00d-1 , 1.25d+0 , 3.62d-1 , 6.87d-3 , 0.d0 , 0.d0 ,
c     x            3.75d-1 , 3.62d-1 , 1.29d+0 , 1.84d-2 , 0.d0 , 0.d0 ,
c     x            -2.89d-3 , 6.87d-3 , 1.84d-2 , 4.30d-1 , 0.d0, 0.d0 ,
c     x            0.d0 , 0.d0 , 0.d0 , 0.d0, 4.55d-1 , 0.d0 ,
c     x            0.d0 , 0.d0 , 0.d0 , 0.d0, 0.d0 , 4.63d-1 /
      cmat(1,1) = {C11}
      cmat(1,2) = {C12}
      cmat(1,3) = {C13}
      cmat(1,4) = {C14}
      cmat(1,5) = {C15}
      cmat(1,6) = {C16}
      cmat(2,1) = cmat(1,2)
      cmat(2,2) = {C22}
      cmat(2,3) = {C23}
      cmat(2,4) = {C24}
      cmat(2,5) = {C25}
      cmat(2,6) = {C26}
      cmat(3,1) = cmat(1,3)
      cmat(3,2) = cmat(2,3)
      cmat(3,3) = {C33}
      cmat(3,4) = {C34}
      cmat(3,5) = {C35}
      cmat(3,6) = {C36}
      cmat(4,1) = cmat(1,4)
      cmat(4,2) = cmat(2,4)
      cmat(4,3) = cmat(3,4)
      cmat(4,4) = {C44}
      cmat(4,5) = {C45}
      cmat(4,6) = {C46}
      cmat(5,1) = cmat(1,5)
      cmat(5,2) = cmat(2,5)
      cmat(5,3) = cmat(3,5)
      cmat(5,4) = cmat(4,5)
      cmat(5,5) = {C55}
      cmat(5,6) = {C56}
      cmat(6,1) = cmat(1,6)
      cmat(6,2) = cmat(2,6)
      cmat(6,3) = cmat(3,6)
      cmat(6,4) = cmat(4,6)
      cmat(6,5) = cmat(5,6)
      cmat(6,6) = {C66}

      call invmat66(cmat,smat)

      print*,'C-Tensor in Voigt-Notation'
      call printmat(cmat,6,6,6,6)
      print*,' '
      print*,'S-Tensor in Voigt-Notation'
      call printmat(smat,6,6,6,6)
      
     
      print*,' '
      print*,'Schreiben der Datei: emodul.plt'
      print*,' '

      lmax=200
      mmax=100

      open(unit=21,file='emodul.plt')
  
      write(21,*) 'VARIABLES = "x_1", "x_2", "x_3"'
      write(21,*) 'ZONE F = POINT , I =',lmax+1,' , J =',mmax+1

      open(unit=22,file='gmodul.plt')

      write(22,*) 'VARIABLES = "x_1", "x_2", "x_3"'
      write(22,*) 'ZONE F = POINT , I =',lmax+1,' , J =',mmax+1


      do m=0,mmax 
      phi1=pi/dble(mmax)*dble(m)
      
      call progress(m,mmax)
      
      do l=0,lmax
      phi2=2.d0*pi/dble(lmax)*dble(l)
      
      call trafo(phi1,phi2,amat)

      tmate(1,1)=amat(1,1)**2
      tmate(1,2)=amat(1,2)**2
      tmate(1,3)=amat(1,3)**2
      tmate(1,4)=amat(1,2)*amat(1,3)
      tmate(1,5)=amat(1,1)*amat(1,3)
      tmate(1,6)=amat(1,1)*amat(1,2)

      tmate(2,1)=amat(2,1)**2
      tmate(2,2)=amat(2,2)**2
      tmate(2,3)=amat(2,3)**2
      tmate(2,4)=amat(2,2)*amat(2,3)
      tmate(2,5)=amat(2,1)*amat(2,3)
      tmate(2,6)=amat(2,1)*amat(2,2)

      tmate(3,1)=amat(3,1)**2
      tmate(3,2)=amat(3,2)**2
      tmate(3,3)=amat(3,3)**2
      tmate(3,4)=amat(3,2)*amat(3,3)
      tmate(3,5)=amat(3,1)*amat(3,3)
      tmate(3,6)=amat(3,1)*amat(3,2)

      tmate(4,1)=2.d0*amat(2,1)*amat(3,1)
      tmate(4,2)=2.d0*amat(2,2)*amat(3,2)
      tmate(4,3)=2.d0*amat(2,3)*amat(3,3)
      tmate(4,4)=amat(2,3)*amat(3,2) + amat(2,2)*amat(3,3)
      tmate(4,5)=amat(2,3)*amat(3,1) + amat(2,1)*amat(3,3)
      tmate(4,6)=amat(3,1)*amat(2,2) + amat(2,1)*amat(3,2)
     
      tmate(5,1)=2.d0*amat(1,1)*amat(3,1)
      tmate(5,2)=2.d0*amat(1,2)*amat(3,2)
      tmate(5,3)=2.d0*amat(1,3)*amat(3,3)
      tmate(5,4)=amat(1,3)*amat(3,2) + amat(1,2)*amat(3,3)
      tmate(5,5)=amat(1,3)*amat(3,1) + amat(1,1)*amat(3,3)
      tmate(5,6)=amat(1,2)*amat(3,1) + amat(1,1)*amat(3,2)

      tmate(6,1)=2.d0*amat(1,1)*amat(2,1)
      tmate(6,2)=2.d0*amat(1,2)*amat(2,2)
      tmate(6,3)=2.d0*amat(1,3)*amat(2,3)
      tmate(6,4)=amat(1,3)*amat(2,2) + amat(1,2)*amat(2,3)
      tmate(6,5)=amat(1,3)*amat(2,1) + amat(1,1)*amat(2,3)
      tmate(6,6)=amat(1,2)*amat(2,1) + amat(1,1)*amat(2,2)


      tmats(1,1)=amat(1,1)**2
      tmats(1,2)=amat(1,2)**2
      tmats(1,3)=amat(1,3)**2
      tmats(1,4)=2.d0*amat(1,2)*amat(1,3)
      tmats(1,5)=2.d0*amat(1,1)*amat(1,3)
      tmats(1,6)=2.d0*amat(1,1)*amat(1,2)

      tmats(2,1)=amat(2,1)**2
      tmats(2,2)=amat(2,2)**2
      tmats(2,3)=amat(2,3)**2
      tmats(2,4)=2.d0*amat(2,2)*amat(2,3)
      tmats(2,5)=2.d0*amat(2,1)*amat(2,3)
      tmats(2,6)=2.d0*amat(2,1)*amat(2,2)

      tmats(3,1)=amat(3,1)**2
      tmats(3,2)=amat(3,2)**2
      tmats(3,3)=amat(3,3)**2
      tmats(3,4)=2.d0*amat(3,2)*amat(3,3)
      tmats(3,5)=2.d0*amat(3,1)*amat(3,3)
      tmats(3,6)=2.d0*amat(3,1)*amat(3,2)

      tmats(4,1)=amat(2,1)*amat(3,1)
      tmats(4,2)=amat(2,2)*amat(3,2)
      tmats(4,3)=amat(2,3)*amat(3,3)
      tmats(4,4)=amat(2,3)*amat(3,2) + amat(2,2)*amat(3,3)
      tmats(4,5)=amat(2,3)*amat(3,1) + amat(2,1)*amat(3,3)
      tmats(4,6)=amat(3,1)*amat(2,2) + amat(2,1)*amat(3,2)
     
      tmats(5,1)=amat(1,1)*amat(3,1)
      tmats(5,2)=amat(1,2)*amat(3,2)
      tmats(5,3)=amat(1,3)*amat(3,3)
      tmats(5,4)=amat(1,3)*amat(3,2) + amat(1,2)*amat(3,3)
      tmats(5,5)=amat(1,3)*amat(3,1) + amat(1,1)*amat(3,3)
      tmats(5,6)=amat(1,2)*amat(3,1) + amat(1,1)*amat(3,2)

      tmats(6,1)=amat(1,1)*amat(2,1)
      tmats(6,2)=amat(1,2)*amat(2,2)
      tmats(6,3)=amat(1,3)*amat(2,3)
      tmats(6,4)=amat(1,3)*amat(2,2) + amat(1,2)*amat(2,3)
      tmats(6,5)=amat(1,3)*amat(2,1) + amat(1,1)*amat(2,3)
      tmats(6,6)=amat(1,2)*amat(2,1) + amat(1,1)*amat(2,2)

      call invmat66(tmats,itmats)


      do i=1,6
        do j=1,6
          hilf(i,j)=0.d0
          do k=1,6
            hilf(i,j)=hilf(i,j)+smat(i,k)*itmats(k,j)
          enddo
        enddo
      enddo
      
      do i=1,6
        do j=1,6
          smatneu(i,j)=0.d0
          do k=1,6
            smatneu(i,j)=smatneu(i,j)+tmate(i,k)*hilf(k,j)
          enddo
        enddo
      enddo

c      call printmat(smatneu,6,6,6,6)
c      call weiter

      emod=1.d0/smatneu(1,1)

      e(1)=dcos(phi1)*emod
      e(2)=dsin(phi1)*dcos(phi2)*emod
      e(3)=dsin(phi1)*dsin(phi2)*emod

      write(21,*) (e(k),k=1,3)

      gmod=dsqrt(2.d0)/dsqrt(smatneu(5,5)**2+smatneu(6,6)**2
     x                +2.d0*smatneu(5,6)**2)

      g(1)=dcos(phi1)*gmod
      g(2)=dsin(phi1)*dcos(phi2)*gmod
      g(3)=dsin(phi1)*dsin(phi2)*gmod

      write(22,*) (g(k),k=1,3)

      enddo ! phi2      

      enddo ! phi1

      end
      
c-----7-----------------------------------------------------------------
      subroutine invmat66(mat,imat)

c     EIN
      real*8 mat(6,6)

c     AUS
      real*8 imat(6,6)

c     INTERN
      integer i,j,ipvt(6),info
      real*8 det(2),work(6)

      do i=1,6
	do j=1,6
	  imat(i,j)=mat(i,j)
	enddo
      enddo

      call dgefa(imat,6,6,ipvt,info)
      call dgedi(imat,6,6,ipvt,det,work,01)

      end
c-----7-----------------------------------------------------------------
      subroutine trafo(phi1,phi2,amat)

c     EIN
      real*8 phi1,phi2

c     AUS
      real*8 amat(3,3)

c     INTERN 
      real*8 c1,c2,s1,s2

      c1=dcos(phi1)
      c2=dcos(phi2)
      s1=dsin(phi1)
      s2=dsin(phi2)

      amat(1,1)=c1
      amat(1,2)=s1*c2
      amat(1,3)=s1*s2

      amat(2,1)=-s1
      amat(2,2)=c1*c2
      amat(2,3)=c1*s2

      amat(3,1)=0.d0
      amat(3,2)=-s2
      amat(3,3)=c2

c      amat(2,1)=0.d0
c      amat(2,2)=0.d0
c      amat(2,3)=0.d0

c      amat(3,1)=0.d0
c      amat(3,2)=0.d0
c      amat(3,3)=0.d0

      end
c-----7-----------------------------------------------------------------



