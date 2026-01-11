import fs from 'fs';
import path from 'path';

export type Post = {
    slug: string;
    title: string;
    excerpt: string;
    content: string;
};

export function getPosts(): Post[] {
    const filePath = path.join(process.cwd(), 'content', 'posts.json');
    try {
        const fileContents = fs.readFileSync(filePath, 'utf8');
        return JSON.parse(fileContents);
    } catch (error) {
        console.error("Error reading posts:", error);
        return [];
    }
}

export function getPostBySlug(slug: string): Post | undefined {
    const posts = getPosts();
    return posts.find((post) => post.slug === slug);
}
