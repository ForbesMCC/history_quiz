param(
  [Parameter(Position=0)][string]$ArgsString
)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = $root
if ($ArgsString) {
  py -3.11 -m history_quiz $ArgsString
} else {
  py -3.11 -m history_quiz --help
}