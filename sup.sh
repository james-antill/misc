#! /bin/sh -e

# Configure priority packages...
conf_priority="kernel yum dnf rpm"

a=""
x="xxxx"

while [ "x$1" != "x" ]; do
   case $1 in
     -*)
        a="$a $1"
        ;;
      *)
        x="$x,$1"
        ;;
   esac
   shift
done

# Priority packages...
ppkgs="$(sudo yum repoquery --upgrades -x $x $conf_priority )"

if [ "x$ppkgs" != "x" ]; then
  sudo yum upgrade $a $conf_priority
fi

pkgs="$(sudo yum repoquery --upgrades -x $x | head -n 1)"

if [ "x$pkgs" = "x" ]; then
 exit 0
fi

sudo yum upgrade $a $pkgs

