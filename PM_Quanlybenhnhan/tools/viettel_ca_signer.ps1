# Local USB signer. Listens on 127.0.0.1:17611 and shows the token PIN dialog.
# Doctors start this by double-clicking Ky_USB_ViettelCA.cmd.
# POST /sign {xml} returns Base64 of an XML Signature (XMLDSig) over that document.

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
Add-Type -AssemblyName System.Security

$prefix = 'http://127.0.0.1:17611/'
$xmlDsig = 'http://www.w3.org/2000/09/xmldsig#'

function Get-SigningCert {
    $certs = @(Get-ChildItem Cert:\CurrentUser\My | Where-Object {
            $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date)
        })
    $preferred = $certs | Where-Object { $_.Issuer -match 'Viettel-CA|VNPT|SmartCA' } |
        Sort-Object NotAfter -Descending |
        Select-Object -First 1
    if ($preferred) { return $preferred }
    return $certs | Sort-Object NotAfter -Descending | Select-Object -First 1
}

function New-XmlSignature([string]$xml) {
    $cert = Get-SigningCert
    if (-not $cert) { throw 'no_cert' }
    $doc = New-Object System.Xml.XmlDocument
    $doc.PreserveWhitespace = $true
    $doc.LoadXml($xml)

    $privateKey = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($cert)
    $publicKey = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPublicKey($cert)
    if (-not $privateKey) { throw 'no_cert' }

    $signed = New-Object System.Security.Cryptography.Xml.SignedXml($doc)
    $signed.SigningKey = $privateKey
    $signed.SignedInfo.CanonicalizationMethod = [System.Security.Cryptography.Xml.SignedXml]::XmlDsigC14NTransformUrl
    $signed.SignedInfo.SignatureMethod = 'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256'
    $signed.Signature.Id = [guid]::NewGuid().ToString()

    $reference = New-Object System.Security.Cryptography.Xml.Reference('')
    $reference.AddTransform((New-Object System.Security.Cryptography.Xml.XmlDsigEnvelopedSignatureTransform))
    $reference.DigestMethod = 'http://www.w3.org/2001/04/xmlenc#sha256'
    $signed.AddReference($reference) | Out-Null

    $keyInfo = New-Object System.Security.Cryptography.Xml.KeyInfo
    $keyInfo.AddClause((New-Object System.Security.Cryptography.Xml.RSAKeyValue($publicKey))) | Out-Null
    $x509 = New-Object System.Security.Cryptography.Xml.KeyInfoX509Data($cert)
    $x509.AddSubjectName($cert.Subject)
    $keyInfo.AddClause($x509) | Out-Null
    $signed.KeyInfo = $keyInfo

    # silent = false so the token PIN dialog opens on this desktop
    $signed.ComputeSignature()
    $signatureXml = $signed.GetXml().OuterXml
    if ($signatureXml -notmatch [regex]::Escape($xmlDsig)) { throw 'sign_failed' }
    return [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($signatureXml))
}

function Send-Json($response, [int]$status, $body) {
    $json = ($body | ConvertTo-Json -Compress)
    $buffer = [Text.Encoding]::UTF8.GetBytes($json)
    $response.StatusCode = $status
    $response.ContentType = 'application/json; charset=utf-8'
    $response.Headers['Access-Control-Allow-Origin'] = '*'
    $response.Headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    $response.Headers['Access-Control-Allow-Headers'] = 'Content-Type'
    $response.ContentLength64 = $buffer.Length
    $response.OutputStream.Write($buffer, 0, $buffer.Length)
    $response.Close()
}

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add($prefix)
try {
    $listener.Start()
} catch {
    Write-Host "Không mở được cổng ký. Nếu cửa sổ ký đang mở thì dùng cửa sổ đó."
    exit 1
}

Write-Host "Chương trình ký USB đang chạy."
Write-Host "Hãy để cửa sổ này mở. Khi bấm Đồng bộ, hộp nhập PIN sẽ hiện ra."

while ($listener.IsListening) {
    $context = $listener.GetContext()
    $request = $context.Request
    $response = $context.Response
    try {
        if ($request.HttpMethod -eq 'OPTIONS') {
            Send-Json $response 204 @{ ok = $true }
            continue
        }
        if ($request.HttpMethod -eq 'GET' -and $request.Url.AbsolutePath -eq '/health') {
            $cert = Get-SigningCert
            Send-Json $response 200 @{
                ok      = $true
                subject = $(if ($cert) { $cert.GetNameInfo('SimpleName', $false) } else { '' })
            }
            continue
        }
        if ($request.HttpMethod -eq 'POST' -and $request.Url.AbsolutePath -eq '/sign') {
            $reader = New-Object IO.StreamReader($request.InputStream, [Text.Encoding]::UTF8)
            $raw = $reader.ReadToEnd()
            $reader.Close()
            $data = $raw | ConvertFrom-Json
            $xml = [string]$data.xml
            if ([string]::IsNullOrWhiteSpace($xml)) { throw 'empty_payload' }
            if ($xml.Length -gt 5000000) { throw 'payload_too_large' }
            $signature = New-XmlSignature $xml
            $cert = Get-SigningCert
            Send-Json $response 200 @{
                signature = $signature
                subject   = $cert.GetNameInfo('SimpleName', $false)
            }
            continue
        }
        Send-Json $response 404 @{ error = 'not_found' }
    } catch {
        $code = $_.Exception.Message
        if ($code -notmatch '^[a-z_]+$') { $code = 'sign_failed' }
        try { Send-Json $response 400 @{ error = $code } } catch {}
    }
}
