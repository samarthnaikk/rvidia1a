FROM node:20-alpine
WORKDIR /app
RUN npm install -g serve
COPY index.html .
EXPOSE 3000
CMD ["serve", "-l", "3000", "."]
