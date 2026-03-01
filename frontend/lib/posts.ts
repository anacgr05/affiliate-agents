import fs from 'fs';
import path from 'path';

export type Post = {
    slug: string;
    title: string;
    excerpt: string;
    content?: string;
    hero?: {
        title: string;
        subtitle: string;
        image: string;
    };
    products?: {
        name: string;
        price: string;
        rating: number;
        pros: string[];
        cons: string[];
        verdict: string;
    }[];
    buying_guide?: {
        steps: {
            title: string;
            content: string;
        }[];
    };
    faq?: {
        question: string;
        answer: string;
    }[];
};

export function getPosts(): Post[] {
    const possiblePaths = [
        path.join(process.cwd(), 'content', 'posts.json'),
        path.join(process.cwd(), 'frontend', 'content', 'posts.json'),
        path.join(process.cwd(), '..', 'frontend', 'content', 'posts.json'),
    ];

    let filePath = "";
    for (const p of possiblePaths) {
        if (fs.existsSync(p)) {
            filePath = p;
            break;
        }
    }

    console.log("🔍 Looking for posts in:", possiblePaths);
    console.log("✅ Found posts at:", filePath);

    if (!filePath) {
        console.error("❌ Posts file not found in any expected location.");
        return [];
    }

    try {
        const fileContents = fs.readFileSync(filePath, 'utf8');
        const posts = JSON.parse(fileContents);
        console.log(`✅ Loaded ${posts.length} posts.`);
        return posts;
    } catch (error) {
        console.error("Error reading posts:", error);
        return [];
    }
}

export function getPostBySlug(slug: string): Post | undefined {
    const posts = getPosts();
    return posts.find((post) => post.slug === slug);
}
