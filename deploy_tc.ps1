<#
.SYNOPSIS
MAICA-MTTS 后端自动化部署脚本

.DESCRIPTION
本脚本用于在Windows系统上全自动部署MAICA-MTTS后端服务，支持镜像源切换和依赖自动安装。
#>

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName Microsoft.VisualBasic

# 初始化全局变量
$global:mirror = $false
$global:installPath = ""
$global:installFlash = $false
$global:enableLoginCheck = $true
$global:startingLogic = $false

# 镜像源替换函数
function Replace-Mirror {
    param($url)
    if ($global:mirror) {
        $url = $url -replace "github.com","ghproxy.com/https://github.com"
        $url = $url -replace "huggingface.co","hf-mirror.com"
    }
    return $url
}

# 环境变量刷新函数
function Refresh-Environment {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + 
                [System.Environment]::GetEnvironmentVariable("Path", "User")
}

# 创建Python软链接
function Create-PythonSymlinks {
    $pyInstallPaths = @{
        "3.8"  = "C:\Program Files\Python38"
        "3.10" = "C:\Program Files\Python310"
        "3.12" = "C:\Program Files\Python312"
    }

    foreach ($ver in $pyInstallPaths.Keys) {
        $pythonDir = $pyInstallPaths[$ver]
        $pythonExe = Join-Path $pythonDir "python.exe"
        $symlinkExe = Join-Path $pythonDir "python$ver.exe"
        
        if (Test-Path $pythonExe -PathType Leaf) {
            if (-not (Test-Path $symlinkExe)) {
                Start-Process cmd -ArgumentList "/c mklink `"$symlinkExe`" `"$pythonExe`"" -Verb RunAs -Wait
            }
        }
    }
}

# 依赖检查函数
function Check-Dependency {
    # 检查Git
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Host "检测到未安装Git，正在尝试自动安装..."
        $url = Replace-Mirror "https://github.com/git-for-windows/git/releases/download/v2.45.1.windows.1/Git-2.45.1-64-bit.exe"
        Invoke-WebRequest $url -OutFile "$env:TEMP\GitInstaller.exe"
        Start-Process "$env:TEMP\GitInstaller.exe" -ArgumentList "/VERYSILENT /NORESTART" -Wait
        Refresh-Environment
    }

    # 检查Python版本并创建软链接
    $pyVersions = @("3.8", "3.10", "3.12")
    $pyInstallPaths = @{
        "3.8"  = "C:\Program Files\Python38"
        "3.10" = "C:\Program Files\Python310"
        "3.12" = "C:\Program Files\Python312"
    }
    foreach ($ver in $pyVersions) {
        if (-not (Get-Command "python$ver" -ErrorAction SilentlyContinue)) {
            Write-Host "检测到未注册Python $ver，正在寻找安装..."
            if (-not (Test-Path $pyInstallPaths[$ver])) {
                Write-Host "检测到未安装Python $ver，正在尝试安装..."
                $url = Replace-Mirror "https://www.python.org/ftp/python/$ver.0/python-$ver.0-amd64.exe"
                Invoke-WebRequest $url -OutFile "$env:TEMP\python$ver.exe"
                Start-Process "$env:TEMP\python$ver.exe" -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait
                Refresh-Environment
            }
        }
    }

    #检查rust和cargo
    if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
        Write-Host "检测到未安装Cargo，正在尝试自动安装..."
        $rustupUrl = "https://win.rustup.rs"
        $rustupPath = "$env:TEMP\rustup-init.exe"
        Invoke-WebRequest -Uri $rustupUrl -OutFile $rustupPath
        
        # 静默安装 Rust 和 Cargo
        & $rustupPath -y
        
        # # 添加 Cargo 到系统环境变量
        # $cargoPath = "$env:USERPROFILE\.cargo\bin"
        # $systemPath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
        
        # if ($systemPath -split ';' -notcontains $cargoPath) {
        #     $newPath = $systemPath + ';' + $cargoPath
        #     [Environment]::SetEnvironmentVariable('Path', $newPath, 'Machine')
        # }    
    }

    Create-PythonSymlinks  # 创建版本化python命令
}

# 显示GUI输入框
function Show-InputDialog {
    $form = New-Object System.Windows.Forms.Form
    $form.Text = '部署配置'
    $form.Size = New-Object System.Drawing.Size(400,300)

    # 安装路径选择
    $labelPath = New-Object System.Windows.Forms.Label
    $labelPath.Text = "选择安装目录:"
    $labelPath.Location = New-Object System.Drawing.Point(10,20)
    $form.Controls.Add($labelPath)

    $textBoxPath = New-Object System.Windows.Forms.TextBox
    $textBoxPath.Location = New-Object System.Drawing.Point(10,50)
    $textBoxPath.Size = New-Object System.Drawing.Size(250,20)
    $form.Controls.Add($textBoxPath)

    $buttonBrowse = New-Object System.Windows.Forms.Button
    $buttonBrowse.Text = "浏览"
    $buttonBrowse.Location = New-Object System.Drawing.Point(270,50)
    $buttonBrowse.Add_Click({
        $folderDialog = New-Object System.Windows.Forms.FolderBrowserDialog
        if ($folderDialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            $textBoxPath.Text = $folderDialog.SelectedPath
        }
    })
    $form.Controls.Add($buttonBrowse)

    # Flash安装选项
    $checkFlash = New-Object System.Windows.Forms.CheckBox
    $checkFlash.Text = "安装flash-attention（需要较长时间）"
    $checkFlash.Location = New-Object System.Drawing.Point(10,100)
    $form.Controls.Add($checkFlash)

    # 登录验证选项
    $checkLogin = New-Object System.Windows.Forms.CheckBox
    $checkLogin.Text = "启用登录验证"
    $checkLogin.Checked = $true
    $checkLogin.Location = New-Object System.Drawing.Point(10,130)
    $form.Controls.Add($checkLogin)

    # 镜像源选项
    $checkMirror = New-Object System.Windows.Forms.CheckBox
    $checkMirror.Text = "使用国内镜像源"
    $checkMirror.Location = New-Object System.Drawing.Point(10,160)
    $form.Controls.Add($checkMirror)

    # 确认按钮
    $buttonOk = New-Object System.Windows.Forms.Button
    $buttonOk.Text = "开始部署"
    $buttonOk.Location = New-Object System.Drawing.Point(150,200)
    $buttonOk.Add_Click({
        $global:installPath = $textBoxPath.Text
        $global:installFlash = $checkFlash.Checked
        $global:enableLoginCheck = $checkLogin.Checked
        $global:startingLogic = $true
        $global:mirror = $checkMirror.Checked
        $form.Close()
    })
    $form.Controls.Add($buttonOk)

    $form.ShowDialog() | Out-Null
}

# 主程序
Show-InputDialog

if (-not $global:startingLogic) {
    Exit 0
}

# 验证安装路径
if (-not (Test-Path $global:installPath)) {
    New-Item -ItemType Directory -Path $global:installPath | Out-Null
}

# 检查依赖
Check-Dependency

# 主部署流程
try {
    Set-Location $global:installPath

    # 克隆仓库
    $repos = @(
        @{url="https://github.com/2noise/ChatTTS.git"; name="ChatTTS"},
        @{url="https://github.com/svc-develop-team/so-vits-svc.git"; name="so-vits-svc"},
        @{url="https://github.com/Mon1-innovation/MAICA_MTTS.git"; name="MAICA_MTTS"}
    )

    foreach ($repo in $repos) {
        $url = Replace-Mirror $repo.url
        if (-not (Test-Path "./$($repo.name)")) {
            git clone $url
        }
    }

    # 切换版本
    Set-Location "./ChatTTS"
    git checkout tags/v0.2.3
    Set-Location "../so-vits-svc"
    git checkout 4.1-Stable
    Set-Location ..

    # 安装依赖
    Set-Location "./ChatTTS"
    python3.10 -m pip install -r requirements.txt
    python3.10 -m pip install -e .
    if ($global:installFlash) {
        python3.10 -m pip install flash-attn --no-build-isolation
    }

    Set-Location "../so-vits-svc"
    python3.8 -m pip install -r requirements.txt

    Set-Location "../MAICA_MTTS"
    python3.12 -m pip install -r requirements.txt

    Set-Location ".."

    # 下载模型文件
    $modelUrl = Replace-Mirror "https://huggingface.co/edgeinfinity/MTTSv0-VoiceClone/resolve/main/G_10400.pth"
    if (-not (Test-Path "./MAICA_MTTS/injection/logs/44k/G_10400.pth")) {
        New-Item -ItemType Directory -Path "./MAICA_MTTS/injection/logs/44k" -Force
        Invoke-WebRequest $modelUrl -OutFile "./MAICA_MTTS/injection/logs/44k/G_10400.pth"
    }

    # 复制文件
    Copy-Item -Path "./MAICA_MTTS/injection/logs/*" -Destination "./so-vits-svc/logs" -Recurse
    Copy-Item -Path "./MAICA_MTTS/injection/svc_serve.py" -Destination "./so-vits-svc"
    Copy-Item -Path "./MAICA_MTTS/injection/tts_serve.py" -Destination "./ChatTTS/examples/api"

    # 创建.env文件
    $envContent = @"
LOGIN_VERIFICATION = "$(if ($global:enableLoginCheck) {"enabled"} else {"disabled"})"
VFC_URL = "https://maicadev.monika.love/api/legality"
CHATTTS_URL = "http://127.0.0.1:8000/generate_voice"
SOCSVC_URL = "http://127.0.0.1:6842/change_voice"
"@
    Set-Content -Path "./MAICA_MTTS/.env" -Value $envContent

    # 完成提示
    [System.Windows.Forms.MessageBox]::Show("部署完成！请按以下顺序启动服务：
    1. 在PowerShell中运行：python3.8 ./so-vits-svc/svc_serve.py
    2. 新窗口运行：python3.10 -m uvicorn ChatTTS.examples.api.tts_serve:app --port 8000
    3. 最后运行：python3.12 ./MAICA_MTTS/mtts.py", "部署成功")

}
catch {
    [System.Windows.Forms.MessageBox]::Show("部署过程中出现错误：$_", "错误", "OK", "Error")
}