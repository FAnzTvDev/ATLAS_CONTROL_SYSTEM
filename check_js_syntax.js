const fs = require('fs');
const html = fs.readFileSync('/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/auto_studio_tab.html', 'utf8');

// Extract script content
const scriptMatch = html.match(/<script[^>]*>([\s\S]*?)<\/script>/gi);
if (!scriptMatch) {
    console.log('No script tags found');
    process.exit(1);
}

let jsCode = '';
scriptMatch.forEach(match => {
    const inner = match.replace(/<script[^>]*>/i, '').replace(/<\/script>/i, '');
    jsCode += inner + '\n';
});

// Try to parse it
try {
    new Function(jsCode);
    console.log('✅ JavaScript syntax is VALID');
    console.log('   Total JS size: ' + jsCode.length + ' chars');

    // Check for key functions
    const funcs = [
        'selectGenre', 'selectProfile', 'sendIdea',
        'loadShotsReview', 'renderShotsReview', 'saveAllShotEdits',
        'proceedToRendering', 'startVideoRendering',
        'startLiveGenPolling', 'stopLiveGenPolling',
        'escapeHtml', 'markShotEdited'
    ];

    funcs.forEach(f => {
        if (jsCode.includes('function ' + f)) {
            console.log('   ✅ ' + f + '() defined');
        } else if (jsCode.includes(f + ' =') || jsCode.includes(f + '(')) {
            console.log('   ✅ ' + f + ' found');
        } else {
            console.log('   ❌ ' + f + ' NOT FOUND');
        }
    });
} catch (e) {
    console.log('❌ JavaScript syntax ERROR:');
    console.log(e.message);

    // Try to find the error location
    const lines = jsCode.split('\n');
    const match = e.message.match(/line (\d+)/i);
    if (match) {
        const lineNum = parseInt(match[1]);
        console.log('\nNear line ' + lineNum + ':');
        for (let i = Math.max(0, lineNum - 3); i < Math.min(lines.length, lineNum + 3); i++) {
            console.log((i === lineNum - 1 ? '>>> ' : '    ') + lines[i]);
        }
    }
}
