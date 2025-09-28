git checkout origin/main -- posts
git add -A
git commit -m "Auto-deploy $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
git push origin main