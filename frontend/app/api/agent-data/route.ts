import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET() {
    const logsPath = path.join(process.cwd(), '../logs/conversation_history.md');
    const memoryPath = path.join(process.cwd(), '../agents/memory_db'); // This is a binary DB, we can't read it directly easily without python.
    // For now, let's just read the logs.

    let logs = "";
    try {
        logs = fs.readFileSync(logsPath, 'utf8');
    } catch (e) {
        logs = "No logs found.";
    }

    return NextResponse.json({ logs });
}
