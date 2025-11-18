function checkPythonInfo() {
    fetch('/api/python/check')
        .then(res => res.json())
        .then(data => {
            const info = document.getElementById('pythonInfo');
            const compatible = data.compatible ? '✅' : '❌';
            info.innerHTML = `
                <div><strong>Current Version:</strong> ${data.version} ${compatible}</div>
                <div><strong>Recommended:</strong> ${data.recommended}</div>
                <div><strong>Executable:</strong> ${data.executable}</div>
            `;
        });
}

function scanPythonEnvironments() {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Scanning...';

    fetch('/api/python/find')
        .then(res => res.json())
        .then(data => {
            const list = document.getElementById('pythonList');
            if (data.executables.length === 0) {
                list.innerHTML = '<div style="text-align: center; padding: 12px; color: var(--text-muted);">No Python environments found</div>';
                return;
            }

            list.innerHTML = data.executables.map(env => {
                let statusIcon = '';
                let statusColor = 'var(--text-primary)';
                let statusText = '';

                if (env.current) {
                    statusIcon = '✅ ';
                    statusColor = 'var(--accent-green)';
                    statusText = ' (Current)';
                } else if (env.configured) {
                    statusIcon = '⚙️ ';
                    statusColor = 'var(--accent-blue)';
                    statusText = ' (Configured)';
                    if (env.invalid) {
                        statusIcon = '❌ ';
                        statusColor = 'var(--accent-red)';
                        statusText = ' (Invalid)';
                    }
                } else if (env.source === 'embedded') {
                    statusIcon = '📦 ';
                    statusColor = 'var(--accent-purple)';
                    statusText = ' (Embedded)';
                }

                return `
                    <div style="background: var(--bg-primary); padding: 10px; border-radius: 6px; margin-bottom: 6px; border: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
                        <div style="flex: 1; font-size: 12px;">
                            <div style="color: ${statusColor}; font-weight: ${env.current || env.configured ? '600' : '400'};">
                                ${statusIcon}Python ${env.version}${statusText}
                            </div>
                            <div style="color: var(--text-muted); font-size: 11px; margin-top: 2px; font-family: monospace; word-break: break-all;">${env.path}</div>
                        </div>
                        ${!env.current && !env.invalid ? `<button class="btn" onclick="selectPythonEnv('${env.path.replace(/\\/g, '\\\\')}')" style="padding: 4px 12px; font-size: 12px;">Select</button>` : ''}
                    </div>
                `;
            }).join('');
        })
        .finally(() => {
            btn.disabled = false;
            btn.textContent = currentLanguage === 'zh' ? '扫描 Python 环境' : 'Scan Python Environments';
        });
}

function selectPythonEnv(path) {
    document.getElementById('pythonExecutable').value = path;
}

async function browsePythonPath() {
    const currentLang = document.documentElement.getAttribute('data-lang') || 'zh';
    const messages = {
        zh: {
            prompt: '请粘贴 python.exe 的完整路径：\n\n示例：\nC:\\Python311\\python.exe\nD:\\Anaconda3\\python.exe\nE:\\fuxkcomfy\\FuxkComfy\\FuxkComfy\\python.exe\n\n或者粘贴目录路径，会自动添加 python.exe',
            invalid: '无效路径。请提供完整的 python.exe 路径',
            title: 'Python 路径'
        },
        en: {
            prompt: 'Please paste the full path to python.exe:\n\nExample:\nC:\\Python311\\python.exe\nD:\\Anaconda3\\python.exe\nE:\\fuxkcomfy\\FuxkComfy\\FuxkComfy\\python.exe\n\nOr paste directory path, python.exe will be auto-added',
            invalid: 'Invalid path. Please provide a complete path to python.exe',
            title: 'Python Path'
        }
    };

    const msg = messages[currentLang];
    const path = prompt(msg.prompt);

    if (path && path.trim()) {
        const trimmedPath = path.trim();
        if (trimmedPath.toLowerCase().endsWith('.exe')) {
            document.getElementById('pythonExecutable').value = trimmedPath;
        } else if (trimmedPath.toLowerCase().includes('python')) {
            if (!trimmedPath.toLowerCase().endsWith('\\python.exe')) {
                const fixedPath = trimmedPath.endsWith('\\')
                    ? trimmedPath + 'python.exe'
                    : trimmedPath + '\\python.exe';
                document.getElementById('pythonExecutable').value = fixedPath;
            } else {
                document.getElementById('pythonExecutable').value = trimmedPath;
            }
        } else {
            showCustomAlert(msg.invalid, msg.title);
        }
    }
}

async function savePythonPath() {
    let pythonPath = document.getElementById('pythonExecutable').value.trim();

    if (pythonPath && !pythonPath.toLowerCase().endsWith('.exe')) {
        if (pythonPath.toLowerCase().includes('python')) {
            pythonPath = pythonPath.endsWith('\\')
                ? pythonPath + 'python.exe'
                : pythonPath + '\\python.exe';
            document.getElementById('pythonExecutable').value = pythonPath;
        }
    }

    const config = getAllConfig();
    config.python_executable = pythonPath;

    const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    });

    const currentLang = document.documentElement.getAttribute('data-lang') || 'zh';
    if (res.ok) {
        await showModal(
            currentLang === 'zh' ? '成功' : 'Success',
            currentLang === 'zh' ? 'Python 路径保存成功！' : 'Python path saved successfully!',
            'confirm'
        );
        checkPythonInfo();
    } else {
        await showModal(
            currentLang === 'zh' ? '错误' : 'Error',
            currentLang === 'zh' ? '保存 Python 路径失败' : 'Failed to save Python path',
            'confirm'
        );
    }
}

function checkDependencies() {
    fetch('/api/dependencies/check')
        .then(res => res.json())
        .then(data => {
            const info = document.getElementById('depsInfo');
            const currentLang = document.documentElement.getAttribute('data-lang') || 'zh';
            const pythonInfo = data.using_python
                ? `<div style="color: var(--text-secondary); font-size: 11px; margin-bottom: 8px; font-family: monospace;">${currentLang === 'zh' ? '使用 Python' : 'Using Python'}: ${data.using_python}</div>`
                : '';
            info.innerHTML = `
                ${pythonInfo}
                <div><strong>Total:</strong> ${data.total} | <strong>Installed:</strong> ${data.installed} | <strong>Missing:</strong> ${data.missing}</div>
                ${data.missing > 0 ? '<div style="color: var(--accent-yellow); margin-top: 8px;">Missing: ' + data.missing_packages.map(p => p.name).join(', ') + '</div>' : '<div style="color: var(--accent-green); margin-top: 8px;">All dependencies satisfied!</div>'}
            `;
        });
}

async function installDependencies() {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Installing...';

    const depsInfo = document.getElementById('depsInfo');
    depsInfo.innerHTML = '<div style="color: var(--accent-blue);">⏳ Installing dependencies... Please wait...</div>';

    try {
        const res = await fetch('/api/dependencies/install', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        const data = await res.json();

        const outputFormatted = data.output.replace(/\n/g, '<br>');

        if (data.success) {
            depsInfo.innerHTML = '<div style="color: var(--accent-green); white-space: pre-wrap; font-size: 12px;">' + outputFormatted + '</div>';
            await showModal('Success', 'Dependencies installation completed!', 'confirm');
            checkDependencies();
        } else {
            depsInfo.innerHTML = '<div style="color: var(--accent-yellow); white-space: pre-wrap; font-size: 12px;">' + outputFormatted + '</div>';
            await showModal('Warning', 'Some packages were skipped or failed. Check the output above.', 'confirm');
            checkDependencies();
        }
    } catch (error) {
        depsInfo.innerHTML = '<div style="color: var(--accent-red);">Error: ' + error.message + '</div>';
        await showModal('Error', 'Installation failed: ' + error.message, 'confirm');
    } finally {
        btn.disabled = false;
        btn.textContent = currentLanguage === 'zh' ? '安装缺失依赖' : 'Install Missing';
    }
}

function scanCustomNodes() {
    fetch('/api/nodes/scan')
        .then(res => res.json())
        .then(data => {
            const list = document.getElementById('customNodesList');
            if (data.nodes.length === 0) {
                list.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-muted);">No custom nodes found</div>';
                return;
            }

            list.innerHTML = data.nodes.map(node => `
                <div style="background: var(--bg-primary); padding: 12px; border-radius: 6px; margin-bottom: 8px; border: 1px solid var(--border-color);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <strong style="color: ${node.enabled ? 'var(--accent-green)' : 'var(--accent-red)'};">${node.name}</strong>
                        <div style="display: flex; gap: 4px;">
                            <button class="btn" onclick="toggleNode('${node.name}', ${!node.enabled})" style="padding: 4px 12px; font-size: 12px;">${node.enabled ? 'Disable' : 'Enable'}</button>
                            ${node.is_git_repo ? `<button class="btn" onclick="updateNode('${node.name}')" style="padding: 4px 12px; font-size: 12px;">Update</button>` : ''}
                            <button class="btn btn-danger" onclick="deleteNode('${node.name}')" style="padding: 4px 12px; font-size: 12px;">Delete</button>
                        </div>
                    </div>
                    <div style="font-size: 11px; color: var(--text-muted);">
                        Files: ${node.files_count} | Requirements: ${node.has_requirements ? '✅' : '❌'} | Git: ${node.is_git_repo ? '✅' : '❌'}
                    </div>
                </div>
            `).join('');
        });
}

async function installNodeFromGit() {
    const gitUrl = document.getElementById('gitUrl').value.trim();
    if (!gitUrl) {
        await showModal('Error', 'Please enter a Git repository URL', 'confirm');
        return;
    }

    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Installing...';

    try {
        const res = await fetch('/api/nodes/install', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ git_url: gitUrl })
        });
        const data = await res.json();

        if (data.success) {
            await showModal('Success', data.message, 'confirm');
            document.getElementById('gitUrl').value = '';
            scanCustomNodes();
        } else {
            await showModal('Error', data.message, 'confirm');
        }
    } finally {
        btn.disabled = false;
        btn.textContent = currentLanguage === 'zh' ? '从 Git 安装' : 'Install from Git';
    }
}

async function toggleNode(nodeName, enable) {
    const res = await fetch('/api/nodes/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_name: nodeName, enable })
    });
    const data = await res.json();

    if (data.success) {
        scanCustomNodes();
    } else {
        await showModal('Error', data.message, 'confirm');
    }
}

async function deleteNode(nodeName) {
    const confirmed = await showModal('Warning', `Delete custom node "${nodeName}"?`, 'delete');
    if (!confirmed) return;

    const res = await fetch('/api/nodes/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_name: nodeName })
    });
    const data = await res.json();

    if (data.success) {
        scanCustomNodes();
    } else {
        await showModal('Error', data.message, 'confirm');
    }
}

async function updateNode(nodeName) {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Updating...';

    try {
        const res = await fetch('/api/nodes/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ node_name: nodeName })
        });
        const data = await res.json();

        if (data.success) {
            await showModal('Success', 'Node updated successfully!', 'confirm');
            scanCustomNodes();
        } else {
            await showModal('Error', data.message, 'confirm');
        }
    } finally {
        btn.disabled = false;
        btn.textContent = 'Update';
    }
}

async function searchNodesByAuthor() {
    const authorName = document.getElementById('authorSearch').value.trim();
    const resultsDiv = document.getElementById('nodeSearchResults');

    if (!authorName) {
        await showModal('Error', currentLanguage === 'zh' ? '请输入作者名称' : 'Please enter an author name', 'confirm');
        return;
    }

    resultsDiv.innerHTML = `<div style="text-align: center; padding: 20px; color: var(--text-muted);">${currentLanguage === 'zh' ? '搜索中...' : 'Searching...'}</div>`;

    try {
        const searchQuery = `user:${encodeURIComponent(authorName)} topic:comfyui OR topic:comfyui-nodes OR comfyui in:name OR comfyui in:description`;
        const apiUrl = `https://api.github.com/search/repositories?q=${encodeURIComponent(searchQuery)}&sort=stars&per_page=50`;

        const res = await fetch(apiUrl, {
            headers: {
                'Accept': 'application/vnd.github.v3+json'
            }
        });

        if (res.status === 403) {
            const resetTime = res.headers.get('X-RateLimit-Reset');
            const resetDate = resetTime ? new Date(resetTime * 1000).toLocaleTimeString() : 'unknown';
            throw new Error(currentLanguage === 'zh'
                ? `GitHub API 速率限制，请在 ${resetDate} 后重试`
                : `GitHub API rate limit exceeded. Try again after ${resetDate}`);
        }

        if (!res.ok) {
            const errorData = await res.json().catch(() => ({}));
            throw new Error(errorData.message || `GitHub API request failed (${res.status})`);
        }

        const data = await res.json();

        if (!data.items || data.items.length === 0) {
            resultsDiv.innerHTML = `<div style="text-align: center; padding: 20px; color: var(--text-muted);">${currentLanguage === 'zh' ? '未找到该作者的仓库' : 'No repositories found for this author'}</div>`;
            return;
        }

        resultsDiv.innerHTML = data.items.map(repo => `
            <div style="background: var(--bg-primary); padding: 12px; border-radius: 6px; margin-bottom: 8px; border: 1px solid var(--border-color);">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;">
                    <div style="flex: 1; min-width: 0;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                            <strong style="color: var(--accent-blue); font-size: 14px;">${repo.name}</strong>
                            <span style="font-size: 11px; color: var(--text-muted);">⭐ ${repo.stargazers_count}</span>
                        </div>
                        <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; line-height: 1.4;">
                            ${repo.description || (currentLanguage === 'zh' ? '无描述' : 'No description')}
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted);">
                            ${currentLanguage === 'zh' ? '更新于' : 'Updated'}: ${new Date(repo.updated_at).toLocaleDateString()}
                        </div>
                    </div>
                    <button class="btn btn-success" onclick="installNodeFromUrl('${repo.clone_url}')" style="padding: 6px 16px; font-size: 12px; white-space: nowrap;">
                        ${currentLanguage === 'zh' ? '安装' : 'Install'}
                    </button>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Search error:', error);
        resultsDiv.innerHTML = `
            <div style="text-align: center; padding: 20px; color: var(--accent-red);">
                <div style="margin-bottom: 12px; font-weight: bold;">${currentLanguage === 'zh' ? '搜索失败' : 'Search Failed'}</div>
                <div style="font-size: 13px; color: var(--text-secondary);">${error.message}</div>
                <div style="margin-top: 16px; font-size: 12px; color: var(--text-muted);">
                    ${currentLanguage === 'zh'
                        ? '提示：您可以直接在"工具"标签的"自定义节点"中输入Git仓库地址安装'
                        : 'Tip: You can install nodes directly by entering Git URL in "Custom Nodes" section in Tools tab'}
                </div>
            </div>
        `;
    }
}

async function installNodeFromUrl(gitUrl) {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Installing...';

    try {
        const res = await fetch('/api/nodes/install', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ git_url: gitUrl })
        });
        const data = await res.json();

        if (data.success) {
            await showModal('Success', data.message, 'confirm');
            scanCustomNodes();
        } else {
            await showModal('Error', data.message, 'confirm');
        }
    } finally {
        btn.disabled = false;
        btn.textContent = 'Install';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const hfSavePath = document.getElementById('hfSavePath');
    const hfCustomPathGroup = document.getElementById('hfCustomPathGroup');

    if (hfSavePath && hfCustomPathGroup) {
        hfSavePath.addEventListener('change', function() {
            if (this.value === 'custom') {
                hfCustomPathGroup.style.display = 'block';
            } else {
                hfCustomPathGroup.style.display = 'none';
            }
        });
    }
});

async function downloadHuggingFaceModel() {
    const modelUrl = document.getElementById('hfModelUrl').value.trim();
    const savePathSelect = document.getElementById('hfSavePath').value;
    const customPath = document.getElementById('hfCustomPath').value.trim();
    const statusDiv = document.getElementById('hfDownloadStatus');

    if (!modelUrl) {
        statusDiv.innerHTML = '<div style="color: #ef4444; padding: 8px; background: rgba(239, 68, 68, 0.1); border-radius: 4px;">Please enter a model URL or ID</div>';
        return;
    }

    const savePath = savePathSelect === 'custom' ? customPath : savePathSelect;

    if (!savePath) {
        statusDiv.innerHTML = '<div style="color: #ef4444; padding: 8px; background: rgba(239, 68, 68, 0.1); border-radius: 4px;">Please specify a save path</div>';
        return;
    }

    statusDiv.innerHTML = '<div style="color: #3b82f6; padding: 8px; background: rgba(59, 130, 246, 0.1); border-radius: 4px;">Starting download...</div>';

    try {
        const res = await fetch('/api/huggingface/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model_url: modelUrl,
                save_path: savePath
            })
        });

        const data = await res.json();

        if (data.success) {
            statusDiv.innerHTML = '<div style="color: #10b981; padding: 8px; background: rgba(16, 185, 129, 0.1); border-radius: 4px;">Download started! Check logs for progress.</div>';
        } else {
            statusDiv.innerHTML = `<div style="color: #ef4444; padding: 8px; background: rgba(239, 68, 68, 0.1); border-radius: 4px;">Error: ${data.error || 'Unknown error'}</div>`;
        }
    } catch (error) {
        statusDiv.innerHTML = `<div style="color: #ef4444; padding: 8px; background: rgba(239, 68, 68, 0.1); border-radius: 4px;">Network error: ${error.message}</div>`;
    }
}
