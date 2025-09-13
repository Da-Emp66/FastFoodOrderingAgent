# FastFoodOrderingAgent   :calling: :arrow_right: &#x1F916 :arrow_right: :hamburger: :fries:
A prototype application enabling users to issue voice or text commands to create and send a food order to fast food company sites. McDonald's site will be supported first.

[Project Management Crash Site Doc](https://docs.google.com/document/d/13NI7L9T9Er9HpxaoRiZk-KD-j6lIgyttm02fnWIr62I/edit?tab=t.0): where all our links go during this application's development.

## Application Set-up

    cp .env.template .env
    . install-cuda.sh
    . install-docker.sh
    docker compose build
    docker compose up -d

Then go to http://localhost:10000/ to view application logs.

## Frontend Set-up

### Docker Build

    cd ui
    docker compose build

### Local Development

    cd ui
    npm install
    npm run dev

## Backend Set-up

### Docker Build

    cd python/fastfoodordering
    docker compose build

### Local Development

    cd python/fastfoodordering
    wget -qO- https://astral.sh/uv/install.sh | sh
    uv sync
