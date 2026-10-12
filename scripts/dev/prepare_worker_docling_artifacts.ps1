$ErrorActionPreference = 'Stop'

$repository = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$artifactRoot = Join-Path $repository '.cache\docling-artifacts'
$hfCommand = Get-Command hf -ErrorAction Stop

$repositories = @(
    @{
        Name = 'docling-project/docling-layout-heron'
        Revision = '8f39ad3c0b4c58e9c2d2c84a38465abf757272d8'
        Directory = 'docling-project--docling-layout-heron'
        Files = @(
            @{ Path = 'model.safetensors'; Sha256 = '00333a43451945aaf89db8ca9c0a17e75d1537c17db60fdb91aa95f4c7929e0c' }
        )
    },
    @{
        Name = 'docling-project/docling-models'
        Revision = '2199320848bb9a8a519d22e4b528185a4f9a6f64'
        Directory = 'docling-models'
        Files = @(
            @{ Path = 'model_artifacts/tableformer/accurate/tableformer_accurate.safetensors'; Sha256 = '2a7d6c924b3cd12fb99a09280ca9c33a89c5d60b93253617d2e088c1a40374d9' },
            @{ Path = 'model_artifacts/tableformer/fast/tableformer_fast.safetensors'; Sha256 = '3119563aab5a7c96fda4d621119b63fd8806272b86c30936d15507616422f718' }
        )
    }
)

foreach ($repositorySource in $repositories) {
    $destination = Join-Path $artifactRoot $repositorySource.Directory
    & $hfCommand.Source download $repositorySource.Name `
        --revision $repositorySource.Revision `
        --local-dir $destination `
        --quiet
    if ($LASTEXITCODE -ne 0) {
        throw "无法下载固定版本的 Docling 模型：$($repositorySource.Name)"
    }
    foreach ($file in $repositorySource.Files) {
        $path = Join-Path $destination $file.Path
        $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $file.Sha256) {
            throw "Docling 模型文件摘要不匹配：$($repositorySource.Name)/$($file.Path)"
        }
    }
}

Write-Output 'DOCLING_WORKER_ARTIFACTS=PASS'
