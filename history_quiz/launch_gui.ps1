# Always run the GUI, regardless of current working directory.
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = $root
py -3.11 -m history_quiz.gui