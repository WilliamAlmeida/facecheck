# Expõe a porta 8090 do WSL (facecheck_api) na rede local do Windows.
# O WSL2 em modo NAT só encaminha para 127.0.0.1; para celular/tablet no mesmo Wi-Fi
# é preciso um portproxy para o IP interno do WSL (que muda a cada reboot) e uma regra de firewall.
# Rodar como administrador. Repetir após reiniciar o Windows.
param(
    [int]$Port = 8090,
    [string]$Distro = 'Ubuntu-22.04',
    [string]$Log = ''
)
$out = @()
try {
    $wslIp = (wsl -d $Distro -- hostname -I).Trim().Split(' ')[0]
    if (-not $wslIp) { throw 'não consegui obter o IP do WSL' }
    netsh interface portproxy delete v4tov4 listenport=$Port listenaddress=0.0.0.0 | Out-Null
    netsh interface portproxy add v4tov4 listenport=$Port listenaddress=0.0.0.0 connectport=$Port connectaddress=$wslIp | Out-Null
    $out += "portproxy 0.0.0.0:$Port -> ${wslIp}:$Port"
    $ruleName = "FaceCheck $Port (WSL)"
    if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow -Profile Any | Out-Null
        $out += "firewall: regra '$ruleName' criada"
    } else {
        $out += "firewall: regra '$ruleName' já existia"
    }
    $out += (netsh interface portproxy show v4tov4 | Out-String)
} catch {
    $out += "erro: $($_.Exception.Message)"
}
$out | ForEach-Object { Write-Host $_ }
if ($Log) { $out | Out-File -FilePath $Log -Encoding utf8 }
