#! /bin/sh -e

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

pkgs="$(sudo yum repoquery --upgrades -x $x | head -n 1)"

if [ "x$pkgs" = "x" ]; then
 exit 0
fi

sudo yum upgrade $a $pkgs

