CaptivPortal Local Lab command shortcuts

Files:
- lab-update.cmd  : update Clean Main, then rebase clean ui-work onto origin/main
- lab-preview.cmd : launch local Admin Console preview at http://127.0.0.1:5055/
- lab-test.cmd    : run full local gate on Clean Main: pytest -> compileall -> git diff --check

Expected paths:
C:\CaptivPortal-UI-Preview
C:\CaptivPortal-UI-Work
C:\CaptivPortal-UI-Preview-Tools\preview.py
C:\CaptivPortal-UI-Preview\.venv

Recommended location:
C:\CaptivPortal-Lab\

Then you can run:
C:\CaptivPortal-Lab\lab-update.cmd
C:\CaptivPortal-Lab\lab-preview.cmd
C:\CaptivPortal-Lab\lab-test.cmd
