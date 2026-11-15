# Run one Blender site-context render while sampling system RAM, Blender RAM and GPU memory.
# Aborts ONLY the Blender process it started if free system RAM falls below -MinFreeGB.
param(
    [Parameter(Mandatory)][ValidateSet('daylight','bluehour')][string]$Variant,
    [Parameter(Mandatory)][int]$Width,
    [Parameter(Mandatory)][int]$Height,
    [Parameter(Mandatory)][int]$Samples,
    [Parameter(Mandatory)][string]$OutDir,
    [Parameter(Mandatory)][string]$Report,
    [double]$MinFreeGB = 2.0,
    [switch]$Aov,
    [switch]$NoRender,
    [string[]]$Extra = @()
)
$ErrorActionPreference = 'Stop'
$repo = 'D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14Q'
$bl = 'C:\Program Files\Blender Foundation\Blender 4.2\blender.exe'
$cache = 'D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14K\output\C_T14K_run\model_cache'
$pack = "$repo\output\C_T14Q_run\site_context\context_pack.json"
$env:T14Q_PYDEPS = "$repo\output\C_T14Q_run\pydeps"
$env:PYTHONIOENCODING = 'utf-8'
if ((Test-Path $OutDir) -and (Get-ChildItem $OutDir -Force | Select-Object -First 1)) { throw "Refusing to reuse a non-empty output folder: $OutDir" }
New-Item -ItemType Directory -Force -Path (Split-Path $Report) | Out-Null
$log = "$Report.blender.log"
$args = @('-b','--factory-startup','-P',"$repo\tools\t14q\site_context_scene.py",'--','--cache-dir',$cache,'--pack',$pack,'--out-dir',$OutDir,
          '--variant',$Variant,'--width',$Width,'--height',$Height,'--samples',$Samples)
if ($Aov) { $args += '--aov' }
if ($NoRender) { $args += '--no-render' }
$args += $Extra
function Get-FreeGB { [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 2) }
function Get-Gpu { try { $o = & nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits 2>$null; $p = $o.Split(','); [pscustomobject]@{ used = [int]$p[0]; total = [int]$p[1] } } catch { $null } }
$before = [pscustomobject]@{ free_ram_gb = Get-FreeGB; gpu = Get-Gpu; time = (Get-Date -Format 's') }
$proc = Start-Process -FilePath $bl -ArgumentList $args -WorkingDirectory $repo -PassThru -NoNewWindow -RedirectStandardOutput $log -RedirectStandardError "$log.err"
$minFree = 1e9; $peakBl = 0.0; $peakGpu = 0; $aborted = $false; $samples_n = 0
while (-not $proc.HasExited) {
    Start-Sleep -Milliseconds 700
    $samples_n++
    $free = Get-FreeGB; if ($free -lt $minFree) { $minFree = $free }
    $p = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    if ($p) { $mb = [math]::Round($p.WorkingSet64 / 1GB, 2); if ($mb -gt $peakBl) { $peakBl = $mb } }
    $g = Get-Gpu; if ($g -and $g.used -gt $peakGpu) { $peakGpu = $g.used }
    if ($free -lt $MinFreeGB) { $aborted = $true; Stop-Process -Id $proc.Id -Force; break }
}
$proc.WaitForExit()
$bpeak = (Select-String -Path $log -Pattern 'Peak:([0-9.]+)([MG])' -AllMatches -ErrorAction SilentlyContinue | ForEach-Object { $_.Matches } | ForEach-Object { if ($_.Groups[2].Value -eq 'G') { [double]$_.Groups[1].Value * 1024 } else { [double]$_.Groups[1].Value } } | Measure-Object -Maximum).Maximum
$result = [ordered]@{
    variant = $Variant; width = $Width; height = $Height; samples = $Samples; out_dir = $OutDir
    min_free_ram_gb_allowed = $MinFreeGB; aborted_by_watchdog = $aborted; exit_code = $proc.ExitCode
    before = $before; after = [pscustomobject]@{ free_ram_gb = Get-FreeGB; gpu = Get-Gpu }
    min_free_ram_gb_during = $minFree; peak_blender_working_set_gb = $peakBl; peak_gpu_used_mb = $peakGpu
    blender_reported_peak_mb = $bpeak; monitor_samples = $samples_n
    outputs = @(Get-ChildItem $OutDir -File -ErrorAction SilentlyContinue | ForEach-Object { [pscustomobject]@{ name = $_.Name; bytes = $_.Length } })
}
$result | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $Report
$result | ConvertTo-Json -Depth 5
