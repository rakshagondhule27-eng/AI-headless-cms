# V7 Visual Upgrade

## Goal
Improve the perceived quality and usability of the CMS without changing the project's core Python/SQL/REST/AI architecture.

## User-facing upgrades
1. Dashboard hero section with AI, ML and API visual cues.
2. Content library uses visual cards with cover art, status, category, author and AI score.
3. Editor includes five built-in local cover visuals.
4. Article page displays its selected cover visual.
5. Analytics uses ranked cards and proportional bar visualizations.
6. Responsive navigation and grids support smaller screens.

## Technical change
`Content.image_url` stores the selected local visual path. A lightweight SQLite migration adds the field to an existing database automatically.

## Why local SVGs?
They keep the project self-contained and avoid broken external image links during a college demo. They can later be replaced with uploaded media or a proper media library.
