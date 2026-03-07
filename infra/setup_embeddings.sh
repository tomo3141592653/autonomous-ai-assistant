#!/bin/bash
# Setup script for new machines
# This creates local Embedding DB from scratch

echo "🚀 Setting up Embedding DB for new machine..."
echo "This will generate embeddings for all memories (may take 5-10 minutes)"
echo ""

# Check if embeddings directory exists
if [ -d "memory/embeddings" ]; then
    echo "⚠️  Embeddings directory already exists."
    read -p "Do you want to regenerate from scratch? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
    rm -rf memory/embeddings/*
fi

# Create directory
mkdir -p memory/embeddings

# Generate embeddings
echo "🧠 Generating embeddings..."
uv run infra/generate_embeddings.py

echo "✅ Done! Embedding DB is ready for use."
echo "Note: This is machine-specific and not synced via git."