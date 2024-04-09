Get-ChildItem "." -Filter *.svg |
Foreach-Object {
	inkscape -w 512 -h 512 $_.FullName -o ($_.BaseName + ".png")
}