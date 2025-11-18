function checkPyTorchInfo() {
    fetch('/api/pytorch/info')
        .then(res => res.json())
        .then(data => {
            const info = document.getElementById('pytorchInfo');
            const currentLang = document.documentElement.getAttribute('data-lang') || 'zh';

            if (data.installed) {
                const cudaStatus = data.cuda_available
                    ? '<span style="color: var(--accent-green);">' + (currentLang === 'zh' ? 'CUDA 可用' : 'CUDA Available') + '</span>'
                    : '<span style="color: var(--accent-red);">' + (currentLang === 'zh' ? 'CPU 版本' : 'CPU Only') + '</span>';

                info.innerHTML = '<div><strong>' + (currentLang === 'zh' ? '版本' : 'Version') + ':</strong> ' + data.version + '</div><div><strong>' + (currentLang === 'zh' ? 'CUDA 状态' : 'CUDA Status') + ':</strong> ' + cudaStatus + '</div>' + (data.cuda_version && data.cuda_version !== 'N/A' ? '<div><strong>' + (currentLang === 'zh' ? 'CUDA 版本' : 'CUDA Version') + ':</strong> ' + data.cuda_version + '</div>' : '') + '<div style="color: var(--text-secondary); font-size: 11px; margin-top: 4px;">' + (currentLang === 'zh' ? '使用 Python' : 'Using Python') + ': ' + data.using_python + '</div>';
            } else {
                info.innerHTML = '<div style="color: var(--accent-yellow);">' + (currentLang === 'zh' ? 'PyTorch 未安装' : 'PyTorch not installed') + '</div>';
            }
        });
}

function loadPyTorchVersions() {
    fetch('/api/pytorch/versions')
        .then(res => res.json())
        .then(data => {
            const select = document.getElementById('pytorchVersionSelect');
            select.innerHTML = '<option value="">' + (document.documentElement.getAttribute('data-lang') === 'zh' ? '选择 PyTorch 版本' : 'Select PyTorch Version') + '</option>';

            for (const key in data) {
                const option = document.createElement('option');
                option.value = key;
                option.textContent = data[key];
                select.appendChild(option);
            }
        });
}

async function installPyTorch() {
    const select = document.getElementById('pytorchVersionSelect');
    const version_key = select.value;

    if (!version_key) {
        const currentLang = document.documentElement.getAttribute('data-lang') || 'zh';
        await showModal(
            currentLang === 'zh' ? '错误' : 'Error',
            currentLang === 'zh' ? '请选择一个 PyTorch 版本' : 'Please select a PyTorch version',
            'confirm'
        );
        return;
    }

    const btn = event.target;
    btn.disabled = true;
    const originalText = btn.textContent;
    const currentLang = document.documentElement.getAttribute('data-lang') || 'zh';
    btn.textContent = currentLang === 'zh' ? '安装中...' : 'Installing...';

    try {
        const res = await fetch('/api/pytorch/install', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ version_key: version_key })
        });
        const data = await res.json();

        if (data.success) {
            await showModal(
                currentLang === 'zh' ? '成功' : 'Success',
                currentLang === 'zh' ? 'PyTorch 安装成功！请重启 FuxkComfy。' : 'PyTorch installed successfully! Please restart FuxkComfy.',
                'confirm'
            );
            checkPyTorchInfo();
        } else {
            await showModal(
                currentLang === 'zh' ? '错误' : 'Error',
                currentLang === 'zh' ? 'PyTorch 安装失败，请查看日志' : 'PyTorch installation failed. Check logs for details.',
                'confirm'
            );
        }
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}
